"""Configuration constants for the LiteLLM hot-swap agent."""

from __future__ import annotations

import os


def _normalize_proxy_base_url(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    # Avoid double slashes in downstream requests
    return cleaned.rstrip("/")

AGENT_NAME = "litellm_agent"
AGENT_DESCRIPTION = (
    "A LiteLLM-backed shell that exposes hot-swappable model and prompt controls."
)

DEFAULT_MODEL = os.getenv("LITELLM_MODEL", "openai/gpt-4o-mini")
DEFAULT_PROVIDER = os.getenv("LITELLM_PROVIDER") or None
PROXY_BASE_URL = _normalize_proxy_base_url(
    os.getenv("FF_LLM_PROXY_BASE_URL")
    or os.getenv("LITELLM_API_BASE")
    or os.getenv("LITELLM_BASE_URL")
)

STATE_PREFIX = "app:litellm_agent/"
STATE_MODEL_KEY = f"{STATE_PREFIX}model"
STATE_PROVIDER_KEY = f"{STATE_PREFIX}provider"
STATE_PROMPT_KEY = f"{STATE_PREFIX}prompt"

CONTROL_PREFIX = "[HOTSWAP"
