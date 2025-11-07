"""HTTP client for the Cognee REST API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx


class CogneeApiError(RuntimeError):
    """Raised when the Cognee API returns an error status."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class CogneeApiClient:
    """Async client for interacting with the Cognee service."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        email: str | None = None,
        password: str | None = None,
        timeout: float = 180.0,
    ):
        base = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=base,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers=headers,
        )
        self._email = email
        self._password = password
        self._token: str | None = None

    async def __aenter__(self) -> "CogneeApiClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def ensure_authenticated(self) -> None:
        """Ensure we have a bearer token before making privileged calls."""

        if self._client.headers.get("Authorization") or self._token:
            return

        if not (self._email and self._password):
            # Service might be running with authentication disabled.
            return

        try:
            await self.register_user(self._email, self._password)
        except CogneeApiError as exc:
            if exc.status_code not in (400, 409):
                raise

        token = await self.login(self._email, self._password)
        self._token = token
        self._client.headers["Authorization"] = f"Bearer {token}"

    async def register_user(self, email: str, password: str) -> Any:
        payload = {
            "email": email,
            "password": password,
            "is_active": True,
            "is_verified": True,
        }
        response = await self._client.post("/api/v1/auth/register", json=payload)
        return self._handle_response(response)

    async def login(self, email: str, password: str) -> str:
        data = {"username": email, "password": password}
        response = await self._client.post("/api/v1/auth/login", data=data)
        payload = self._handle_response(response)
        token = payload.get("access_token")
        if not token:
            raise CogneeApiError("Cognee auth response did not include an access_token")
        return token

    async def add_files(self, file_paths: Iterable[Path], dataset_name: str) -> Any:
        await self.ensure_authenticated()
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for path in file_paths:
            data = path.read_bytes()
            files.append(("data", (path.name, data, "application/octet-stream")))

        data = {"datasetName": dataset_name}
        response = await self._client.post("/api/v1/add", data=data, files=files)
        return self._handle_response(response)

    async def add_texts(self, texts: Sequence[str], dataset_name: str) -> Any:
        await self.ensure_authenticated()
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for idx, text in enumerate(texts):
            data = text.encode("utf-8")
            files.append(("data", (f"snippet_{idx}.txt", data, "text/plain")))

        response = await self._client.post(
            "/api/v1/add",
            data={"datasetName": dataset_name},
            files=files,
        )
        return self._handle_response(response)

    async def cognify(self, datasets: Sequence[str]) -> Any:
        await self.ensure_authenticated()
        payload = {"datasets": list(datasets), "run_in_background": False}
        response = await self._client.post("/api/v1/cognify", json=payload)
        return self._handle_response(response)

    async def search(
        self,
        *,
        query: str,
        search_type: str,
        datasets: Sequence[str] | None = None,
        top_k: int | None = None,
        only_context: bool = False,
    ) -> Any:
        await self.ensure_authenticated()
        payload: dict[str, object] = {
            "query": query,
            "search_type": search_type,
            "only_context": only_context,
        }
        if datasets:
            payload["datasets"] = list(datasets)
        if top_k is not None:
            payload["top_k"] = top_k

        response = await self._client.post("/api/v1/search", json=payload)
        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> Any:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - surfaced to caller
            message = exc.response.text
            raise CogneeApiError(
                f"Cognee API request failed ({exc.response.status_code}): {message}",
                status_code=exc.response.status_code,
            ) from exc
        if response.content:
            return response.json()
        return {}
