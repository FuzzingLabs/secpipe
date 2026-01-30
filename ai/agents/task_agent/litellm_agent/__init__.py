"""LiteLLM hot-swap agent package exports."""

from .agent import root_agent
from .callbacks import (
    before_agent_callback,
    before_model_callback,
    provide_instruction,
)
from .config import (
    AGENT_DESCRIPTION,
    AGENT_NAME,
    CONTROL_PREFIX,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    STATE_MODEL_KEY,
    STATE_PROVIDER_KEY,
    STATE_PROMPT_KEY,
)
from .control import (
    HotSwapCommand,
    ModelSpec,
    build_control_message,
    parse_control_message,
    parse_model_spec,
    serialize_model_spec,
)
from .state import HotSwapState, apply_state_to_agent
from .tools import HOTSWAP_TOOLS, get_config, set_model, set_prompt

__all__ = [
    "root_agent",
    "before_agent_callback",
    "before_model_callback",
    "provide_instruction",
    "AGENT_DESCRIPTION",
    "AGENT_NAME",
    "CONTROL_PREFIX",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "STATE_MODEL_KEY",
    "STATE_PROVIDER_KEY",
    "STATE_PROMPT_KEY",
    "HotSwapCommand",
    "ModelSpec",
    "HotSwapState",
    "apply_state_to_agent",
    "build_control_message",
    "parse_control_message",
    "parse_model_spec",
    "serialize_model_spec",
    "HOTSWAP_TOOLS",
    "get_config",
    "set_model",
    "set_prompt",
]
