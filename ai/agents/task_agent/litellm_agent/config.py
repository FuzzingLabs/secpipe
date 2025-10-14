"""Configuration constants for the LiteLLM hot-swap agent."""

from __future__ import annotations

import os

AGENT_NAME = "litellm_agent"
AGENT_DESCRIPTION = (
    "A LiteLLM-backed shell that exposes hot-swappable model and prompt controls."
)

DEFAULT_MODEL = os.getenv("LITELLM_MODEL", "gemini-2.0-flash-001")
DEFAULT_PROVIDER = os.getenv("LITELLM_PROVIDER")

STATE_PREFIX = "app:litellm_agent/"
STATE_MODEL_KEY = f"{STATE_PREFIX}model"
STATE_PROVIDER_KEY = f"{STATE_PREFIX}provider"
STATE_PROMPT_KEY = f"{STATE_PREFIX}prompt"

CONTROL_PREFIX = "[HOTSWAP"
