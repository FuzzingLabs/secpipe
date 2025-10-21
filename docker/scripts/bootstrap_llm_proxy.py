"""Bootstrap the LiteLLM proxy with provider secrets and default virtual keys.

The bootstrapper runs as a one-shot container during docker-compose startup.
It performs the following actions:

  1. Waits for the proxy health endpoint to respond.
  2. Collects upstream provider API keys from the shared .env file (plus any
     legacy copies) and mirrors them into a proxy-specific env file
     (volumes/env/.env.litellm) so only the proxy container can access them.
  3. Emits a default virtual key for the task agent by calling /key/generate,
     persisting the generated token back into volumes/env/.env so the agent can
     authenticate through the proxy instead of using raw provider secrets.
  4. Keeps the process idempotent: existing keys are reused and their allowed
     model list is refreshed instead of issuing duplicates on every run.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

PROXY_BASE_URL = os.getenv("PROXY_BASE_URL", "http://llm-proxy:4000").rstrip("/")
ENV_FILE_PATH = Path(os.getenv("ENV_FILE_PATH", "/bootstrap/env/.env"))
LITELLM_ENV_FILE_PATH = Path(
    os.getenv("LITELLM_ENV_FILE_PATH", "/bootstrap/env/.env.litellm")
)
LEGACY_ENV_FILE_PATH = Path(
    os.getenv("LEGACY_ENV_FILE_PATH", "/bootstrap/env/.env.bifrost")
)
DEFAULT_VIRTUAL_KEY_ALIAS = os.getenv(
    "LITELLM_DEFAULT_KEY_ALIAS", "task-agent default"
)
DEFAULT_VIRTUAL_KEY_USER = os.getenv(
    "LITELLM_DEFAULT_KEY_USER", "fuzzforge-task-agent"
)
PLACEHOLDER_KEY = os.getenv("LITELLM_PLACEHOLDER_KEY", "sk-proxy-default")
DEFAULT_KEY_DURATION = os.getenv("LITELLM_DEFAULT_KEY_DURATION", "7d")
DEFAULT_KEY_BUDGET = os.getenv("LITELLM_DEFAULT_KEY_BUDGET", "25")
MAX_WAIT_SECONDS = int(os.getenv("LITELLM_PROXY_WAIT_SECONDS", "120"))


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    litellm_env_var: str
    alias_env_var: str
    source_env_vars: tuple[str, ...]


# Support fresh LiteLLM variables while gracefully migrating legacy env
# aliases on first boot.
PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "openai",
        "OPENAI_API_KEY",
        "LITELLM_OPENAI_API_KEY",
        ("LITELLM_OPENAI_API_KEY", "BIFROST_OPENAI_KEY"),
    ),
    ProviderSpec(
        "anthropic",
        "ANTHROPIC_API_KEY",
        "LITELLM_ANTHROPIC_API_KEY",
        ("LITELLM_ANTHROPIC_API_KEY", "BIFROST_ANTHROPIC_KEY"),
    ),
    ProviderSpec(
        "gemini",
        "GEMINI_API_KEY",
        "LITELLM_GEMINI_API_KEY",
        ("LITELLM_GEMINI_API_KEY", "BIFROST_GEMINI_KEY"),
    ),
    ProviderSpec(
        "mistral",
        "MISTRAL_API_KEY",
        "LITELLM_MISTRAL_API_KEY",
        ("LITELLM_MISTRAL_API_KEY", "BIFROST_MISTRAL_KEY"),
    ),
    ProviderSpec(
        "openrouter",
        "OPENROUTER_API_KEY",
        "LITELLM_OPENROUTER_API_KEY",
        ("LITELLM_OPENROUTER_API_KEY", "BIFROST_OPENROUTER_KEY"),
    ),
)

PROVIDER_LOOKUP: dict[str, ProviderSpec] = {spec.name: spec for spec in PROVIDERS}


def log(message: str) -> None:
    print(f"[litellm-bootstrap] {message}", flush=True)


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text().splitlines()


def write_lines(path: Path, lines: Iterable[str]) -> None:
    material = "\n".join(lines)
    if material and not material.endswith("\n"):
        material += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(material)


def read_env_file() -> list[str]:
    if not ENV_FILE_PATH.exists():
        raise FileNotFoundError(
            f"Expected env file at {ENV_FILE_PATH}. Copy volumes/env/.env.example first."
        )
    return read_lines(ENV_FILE_PATH)


def write_env_file(lines: Iterable[str]) -> None:
    write_lines(ENV_FILE_PATH, lines)


def read_litellm_env_file() -> list[str]:
    return read_lines(LITELLM_ENV_FILE_PATH)


def write_litellm_env_file(lines: Iterable[str]) -> None:
    write_lines(LITELLM_ENV_FILE_PATH, lines)


def read_legacy_env_file() -> Mapping[str, str]:
    lines = read_lines(LEGACY_ENV_FILE_PATH)
    return parse_env_lines(lines)


def set_env_value(lines: list[str], key: str, value: str) -> tuple[list[str], bool]:
    prefix = f"{key}="
    new_line = f"{prefix}{value}"
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(prefix):
            if stripped == new_line:
                return lines, False
            indent = line[: len(line) - len(stripped)]
            lines[idx] = f"{indent}{new_line}"
            return lines, True
    lines.append(new_line)
    return lines, True


def parse_env_lines(lines: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        mapping[key] = value
    return mapping


def wait_for_proxy() -> None:
    health_paths = ("/health/liveliness", "/health", "/")
    deadline = time.time() + MAX_WAIT_SECONDS
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        for path in health_paths:
            url = f"{PROXY_BASE_URL}{path}"
            try:
                with urllib.request.urlopen(url) as response:  # noqa: S310
                    if response.status < 400:
                        log(f"Proxy responded on {path} (attempt {attempt})")
                        return
            except urllib.error.URLError as exc:
                log(f"Proxy not ready yet ({path}): {exc}")
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for proxy at {PROXY_BASE_URL}")


def request_json(
    path: str,
    *,
    method: str = "GET",
    payload: Mapping[str, object] | None = None,
    auth_token: str | None = None,
) -> tuple[int, str]:
    url = f"{PROXY_BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body


def get_master_key(env_map: Mapping[str, str]) -> str:
    candidate = os.getenv("LITELLM_MASTER_KEY") or env_map.get("LITELLM_MASTER_KEY")
    if not candidate:
        raise RuntimeError(
            "LITELLM_MASTER_KEY is not set. Add it to volumes/env/.env before starting Docker."
        )
    value = candidate.strip()
    if not value:
        raise RuntimeError(
            "LITELLM_MASTER_KEY is blank. Provide a non-empty value in the env file."
        )
    return value


def gather_provider_keys(
    env_lines: list[str],
    env_map: dict[str, str],
    legacy_map: Mapping[str, str],
) -> tuple[dict[str, str], list[str], bool]:
    updated_lines = list(env_lines)
    discovered: dict[str, str] = {}
    changed = False

    for spec in PROVIDERS:
        value: str | None = None
        for source_var in spec.source_env_vars:
            candidate = env_map.get(source_var) or legacy_map.get(source_var) or os.getenv(
                source_var
            )
            if not candidate:
                continue
            stripped = candidate.strip()
            if stripped:
                value = stripped
                break
        if not value:
            continue

        discovered[spec.litellm_env_var] = value
        updated_lines, alias_changed = set_env_value(
            updated_lines, spec.alias_env_var, value
        )
        if alias_changed:
            env_map[spec.alias_env_var] = value
            changed = True

    return discovered, updated_lines, changed


def ensure_litellm_env(provider_values: Mapping[str, str]) -> None:
    if not provider_values:
        log("No provider secrets discovered; skipping LiteLLM env update")
        return
    lines = read_litellm_env_file()
    updated_lines = list(lines)
    changed = False
    for env_var, value in provider_values.items():
        updated_lines, var_changed = set_env_value(updated_lines, env_var, value)
        if var_changed:
            changed = True
    if changed or not lines:
        write_litellm_env_file(updated_lines)
        log(f"Wrote provider secrets to {LITELLM_ENV_FILE_PATH}")


def current_env_key(env_map: Mapping[str, str]) -> str | None:
    candidate = os.getenv("OPENAI_API_KEY") or env_map.get("OPENAI_API_KEY")
    if not candidate:
        return None
    value = candidate.strip()
    if not value or value == PLACEHOLDER_KEY:
        return None
    return value


def collect_default_models(env_map: Mapping[str, str]) -> list[str]:
    explicit = (
        os.getenv("LITELLM_DEFAULT_MODELS")
        or env_map.get("LITELLM_DEFAULT_MODELS")
        or ""
    )
    models: list[str] = []
    if explicit:
        models.extend(
            model.strip()
            for model in explicit.split(",")
            if model.strip()
        )
    if models:
        return sorted(dict.fromkeys(models))

    configured_model = (
        os.getenv("LITELLM_MODEL") or env_map.get("LITELLM_MODEL") or ""
    ).strip()
    configured_provider = (
        os.getenv("LITELLM_PROVIDER") or env_map.get("LITELLM_PROVIDER") or ""
    ).strip()

    if configured_model:
        if "/" in configured_model:
            models.append(configured_model)
        elif configured_provider:
            models.append(f"{configured_provider}/{configured_model}")
    elif configured_provider:
        models.append(f"{configured_provider}/gpt-4o-mini")

    if not models:
        models.append("openai/gpt-4o-mini")

    return sorted(dict.fromkeys(models))


def fetch_existing_key_record(master_key: str, key_value: str) -> Mapping[str, object] | None:
    encoded = urllib.parse.quote_plus(key_value)
    status, body = request_json(f"/key/info?key={encoded}", auth_token=master_key)
    if status != 200:
        log(f"Key lookup failed ({status}); treating OPENAI_API_KEY as new")
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        log("Key info response was not valid JSON; ignoring")
        return None
    if isinstance(data, Mapping) and data.get("key"):
        return data
    return None


def generate_virtual_key(
    master_key: str,
    models: list[str],
) -> str:
    try:
        budget = float(DEFAULT_KEY_BUDGET)
    except ValueError:
        budget = 25.0

    payload: dict[str, object] = {
        "key_alias": DEFAULT_VIRTUAL_KEY_ALIAS,
        "user_id": DEFAULT_VIRTUAL_KEY_USER,
        "models": models,
        "duration": DEFAULT_KEY_DURATION,
        "max_budget": budget,
        "metadata": {
            "provisioned_by": "bootstrap",
            "default_models": models,
        },
        "key_type": "llm_api",
    }
    status, body = request_json(
        "/key/generate", method="POST", payload=payload, auth_token=master_key
    )
    if status not in {200, 201}:
        raise RuntimeError(f"Failed to generate virtual key ({status}): {body}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Virtual key response was not valid JSON") from exc
    if isinstance(data, Mapping):
        key_value = str(data.get("key") or data.get("token") or "").strip()
        if key_value:
            log("Generated new LiteLLM virtual key for the task agent")
            return key_value
    raise RuntimeError("Virtual key response did not include a key field")


def update_virtual_key(
    master_key: str,
    key_value: str,
    models: list[str],
) -> None:
    if not models:
        return
    payload: dict[str, object] = {
        "key": key_value,
        "models": models,
    }
    status, body = request_json(
        "/key/update", method="POST", payload=payload, auth_token=master_key
    )
    if status != 200:
        log(f"Virtual key update skipped ({status}): {body}")
    else:
        log("Refreshed allowed models on existing virtual key")


def persist_key_to_env(new_key: str) -> None:
    lines = read_env_file()
    updated_lines, changed = set_env_value(lines, "OPENAI_API_KEY", new_key)
    if changed:
        write_env_file(updated_lines)
        os.environ["OPENAI_API_KEY"] = new_key
        log(f"Persisted virtual key to {ENV_FILE_PATH}")
    else:
        log("Virtual key already present in env file; no update needed")


def ensure_virtual_key(
    master_key: str,
    models: list[str],
    env_map: Mapping[str, str],
) -> str:
    allowed_models = []
    sync_flag = os.getenv("LITELLM_SYNC_VIRTUAL_KEY_MODELS", "").strip().lower()
    if sync_flag in {"1", "true", "yes", "on"}:
        allowed_models = models
    existing_key = current_env_key(env_map)
    if existing_key:
        record = fetch_existing_key_record(master_key, existing_key)
        if record:
            log("Reusing existing LiteLLM virtual key")
            if allowed_models:
                update_virtual_key(master_key, existing_key, allowed_models)
            return existing_key
        log("Existing OPENAI_API_KEY not registered with proxy; issuing a new key")

    new_key = generate_virtual_key(master_key, models)
    if allowed_models:
        update_virtual_key(master_key, new_key, allowed_models)
    return new_key


def _split_model_identifier(model: str) -> tuple[str | None, str]:
    if "/" in model:
        provider, short_name = model.split("/", 1)
        return provider.lower().strip() or None, short_name.strip()
    return None, model.strip()


def ensure_models_registered(
    master_key: str,
    models: list[str],
    env_map: Mapping[str, str],
) -> None:
    if not models:
        return
    for model in models:
        provider, short_name = _split_model_identifier(model)
        if not provider or not short_name:
            log(f"Skipping model '{model}' (no provider segment)")
            continue
        spec = PROVIDER_LOOKUP.get(provider)
        if not spec:
            log(f"No provider spec registered for '{provider}'; skipping model '{model}'")
            continue
        provider_secret = (
            env_map.get(spec.alias_env_var)
            or env_map.get(spec.litellm_env_var)
            or os.getenv(spec.alias_env_var)
            or os.getenv(spec.litellm_env_var)
        )
        if not provider_secret:
            log(
                f"Provider secret for '{provider}' not found; skipping model registration"
            )
            continue

        api_key_reference = f"os.environ/{spec.alias_env_var}"
        payload: dict[str, object] = {
            "model_name": model,
            "litellm_params": {
                "model": short_name,
                "custom_llm_provider": provider,
                "api_key": api_key_reference,
            },
            "model_info": {
                "provider": provider,
                "description": "Auto-registered during bootstrap",
            },
        }

        status, body = request_json(
            "/model/new", method="POST", payload=payload, auth_token=master_key
        )
        if status in {200, 201}:
            log(f"Registered LiteLLM model '{model}'")
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = body
        error_message = (
            data.get("error") if isinstance(data, Mapping) else str(data)
        )
        if status == 409 or (
            isinstance(error_message, str)
            and "already" in error_message.lower()
        ):
            log(f"Model '{model}' already present; skipping")
            continue
        log(f"Failed to register model '{model}' ({status}): {error_message}")


def main() -> int:
    log("Bootstrapping LiteLLM proxy")
    try:
        wait_for_proxy()
        env_lines = read_env_file()
        env_map = parse_env_lines(env_lines)
        legacy_map = read_legacy_env_file()
        master_key = get_master_key(env_map)

        provider_values, updated_env_lines, env_changed = gather_provider_keys(
            env_lines, env_map, legacy_map
        )
        if env_changed:
            write_env_file(updated_env_lines)
            env_map = parse_env_lines(updated_env_lines)
            log("Updated LiteLLM provider aliases in shared env file")

        ensure_litellm_env(provider_values)

        models = collect_default_models(env_map)
        log("Default models for virtual key: %s" % ", ".join(models))

        virtual_key = ensure_virtual_key(master_key, models, env_map)
        persist_key_to_env(virtual_key)

        ensure_models_registered(master_key, models, env_map)

        log("Bootstrap complete")
        return 0
    except Exception as exc:  # pragma: no cover - startup failure reported to logs
        log(f"Bootstrap failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
