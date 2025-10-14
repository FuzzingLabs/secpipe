"""Session state utilities for the LiteLLM hot-swap agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Optional

from .config import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
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

        kwargs = {"model": self.model}
        if self.provider:
            kwargs["custom_llm_provider"] = self.provider
        return LiteLlm(**kwargs)

    @property
    def display_model(self) -> str:
        if self.provider:
            return f"{self.provider}/{self.model}"
        return self.model


def apply_state_to_agent(invocation_context, state: HotSwapState) -> None:
    """Update the provided agent with a LiteLLM instance matching state."""

    agent = invocation_context.agent
    agent.model = state.instantiate_llm()
