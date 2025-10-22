"""Session state utilities for the LiteLLM hot-swap agent."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping, MutableMapping, Optional

import httpx

from .config import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    PROXY_BASE_URL,
    STATE_MODEL_KEY,
    STATE_PROMPT_KEY,
    STATE_PROVIDER_KEY,
)


@dataclass(slots=True)
class HotSwapState:
    """Lightweight view of the hot-swap session state."""

    model: str = DEFAULT_MODEL
    provider: Optional[str] = None
    prompt: Optional[str] = None

    @classmethod
    def from_mapping(cls, mapping: Optional[Mapping[str, Any]]) -> "HotSwapState":
        if not mapping:
            return cls()

        raw_model = mapping.get(STATE_MODEL_KEY, DEFAULT_MODEL)
        raw_provider = mapping.get(STATE_PROVIDER_KEY)
        raw_prompt = mapping.get(STATE_PROMPT_KEY)

        model = raw_model.strip() if isinstance(raw_model, str) else DEFAULT_MODEL
        provider = raw_provider.strip() if isinstance(raw_provider, str) else None
        if not provider and DEFAULT_PROVIDER:
            provider = DEFAULT_PROVIDER.strip() or None
        prompt = raw_prompt.strip() if isinstance(raw_prompt, str) else None
        return cls(
            model=model or DEFAULT_MODEL,
            provider=provider or None,
            prompt=prompt or None,
        )

    def persist(self, store: MutableMapping[str, object]) -> None:
        store[STATE_MODEL_KEY] = self.model
        if self.provider:
            store[STATE_PROVIDER_KEY] = self.provider
        else:
            store[STATE_PROVIDER_KEY] = None
        store[STATE_PROMPT_KEY] = self.prompt

    def describe(self) -> str:
        prompt_value = self.prompt if self.prompt else "(default prompt)"
        provider_value = self.provider if self.provider else "(default provider)"
        return (
            "📊 Current Configuration\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Model: {self.model}\n"
            f"Provider: {provider_value}\n"
            f"System Prompt: {prompt_value}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )

    def instantiate_llm(self):
        """Create a LiteLlm instance for the current state."""

        from google.adk.models.lite_llm import LiteLlm  # Lazy import to avoid cycle
        from google.adk.models.lite_llm import LiteLLMClient
        from litellm.types.utils import Choices, Message, ModelResponse, Usage

        kwargs = {"model": self.model}
        if self.provider:
            kwargs["custom_llm_provider"] = self.provider
        if PROXY_BASE_URL:
            provider = (self.provider or DEFAULT_PROVIDER or "").lower()
            if provider and provider != "openai":
                kwargs["api_base"] = f"{PROXY_BASE_URL.rstrip('/')}/{provider}"
            else:
                kwargs["api_base"] = PROXY_BASE_URL
        kwargs.setdefault("api_key", os.environ.get("TASK_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY"))

        provider = (self.provider or DEFAULT_PROVIDER or "").lower()
        model_suffix = self.model.split("/", 1)[-1]
        use_responses = provider == "openai" and (
            model_suffix.startswith("gpt-5") or model_suffix.startswith("o1")
        )
        if use_responses:
            kwargs.setdefault("use_responses_api", True)

        llm = LiteLlm(**kwargs)

        if use_responses and PROXY_BASE_URL:

            class _ResponsesAwareClient(LiteLLMClient):
                def __init__(self, base_client: LiteLLMClient, api_base: str, api_key: str):
                    self._base_client = base_client
                    self._api_base = api_base.rstrip("/")
                    self._api_key = api_key

                async def acompletion(self, model, messages, tools, **kwargs):  # type: ignore[override]
                    use_responses_api = kwargs.pop("use_responses_api", False)
                    if not use_responses_api:
                        return await self._base_client.acompletion(
                            model=model,
                            messages=messages,
                            tools=tools,
                            **kwargs,
                        )

                    resolved_model = model
                    if "/" not in resolved_model:
                        resolved_model = f"openai/{resolved_model}"

                    payload = {
                        "model": resolved_model,
                        "input": _messages_to_responses_input(messages),
                    }

                    timeout = kwargs.get("timeout", 60)
                    headers = {
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    }

                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{self._api_base}/v1/responses",
                            json=payload,
                            headers=headers,
                        )
                        try:
                            response.raise_for_status()
                        except httpx.HTTPStatusError as exc:
                            text = exc.response.text
                            raise RuntimeError(
                                f"LiteLLM responses request failed: {text}"
                            ) from exc
                        data = response.json()

                    text_output = _extract_output_text(data)
                    usage = data.get("usage", {})

                    return ModelResponse(
                        id=data.get("id"),
                        model=model,
                        choices=[
                            Choices(
                                finish_reason="stop",
                                index=0,
                                message=Message(role="assistant", content=text_output),
                                provider_specific_fields={"bifrost_response": data},
                            )
                        ],
                        usage=Usage(
                            prompt_tokens=usage.get("input_tokens"),
                            completion_tokens=usage.get("output_tokens"),
                            reasoning_tokens=usage.get("output_tokens_details", {}).get(
                                "reasoning_tokens"
                            ),
                            total_tokens=usage.get("total_tokens"),
                        ),
                    )

            llm.llm_client = _ResponsesAwareClient(
                llm.llm_client,
                PROXY_BASE_URL,
                os.environ.get("TASK_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY", ""),
            )

        return llm

    @property
    def display_model(self) -> str:
        if self.provider:
            return f"{self.provider}/{self.model}"
        return self.model


def apply_state_to_agent(invocation_context, state: HotSwapState) -> None:
    """Update the provided agent with a LiteLLM instance matching state."""

    agent = invocation_context.agent
    agent.model = state.instantiate_llm()


def _messages_to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        text_segments: list[str] = []

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        text_segments.append(str(text))
                elif isinstance(item, str):
                    text_segments.append(item)
        elif isinstance(content, str):
            text_segments.append(content)

        text = "\n".join(segment.strip() for segment in text_segments if segment)
        if not text:
            continue

        entry_type = "input_text"
        if role == "assistant":
            entry_type = "output_text"

        inputs.append(
            {
                "role": role,
                "content": [
                    {
                        "type": entry_type,
                        "text": text,
                    }
                ],
            }
        )

    if not inputs:
        inputs.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "",
                    }
                ],
            }
        )
    return inputs


def _extract_output_text(response_json: dict[str, Any]) -> str:
    outputs = response_json.get("output", [])
    collected: list[str] = []
    for item in outputs:
        if isinstance(item, dict) and item.get("type") == "message":
            for part in item.get("content", []):
                if isinstance(part, dict) and part.get("type") == "output_text":
                    text = part.get("text", "")
                    if text:
                        collected.append(str(text))
    return "\n\n".join(collected).strip()
