"""Tool definitions exposed to the LiteLLM agent."""

from __future__ import annotations

from typing import Optional

from google.adk.tools import FunctionTool, ToolContext

from .control import parse_model_spec
from .state import HotSwapState, apply_state_to_agent


async def set_model(
    model: str,
    *,
    provider: Optional[str] = None,
    tool_context: ToolContext,
) -> str:
    """Hot-swap the active LiteLLM model for this session."""

    spec = parse_model_spec(model, provider=provider)
    state = HotSwapState.from_mapping(tool_context.state)
    state.model = spec.model
    state.provider = spec.provider
    state.persist(tool_context.state)
    try:
        apply_state_to_agent(tool_context._invocation_context, state)
    except Exception as exc:  # pragma: no cover - defensive reporting
        return f"❌ Failed to apply model '{state.display_model}': {exc}"
    return f"✅ Model switched to: {state.display_model}"


async def set_prompt(prompt: str, *, tool_context: ToolContext) -> str:
    """Update or clear the system prompt used for this session."""

    state = HotSwapState.from_mapping(tool_context.state)
    prompt_value = prompt.strip()
    state.prompt = prompt_value or None
    state.persist(tool_context.state)
    if state.prompt:
        return "✅ System prompt updated. This change takes effect immediately."
    return "✅ System prompt cleared. Reverting to default instruction."


async def get_config(*, tool_context: ToolContext) -> str:
    """Return a summary of the current model and prompt configuration."""

    state = HotSwapState.from_mapping(tool_context.state)
    return state.describe()


HOTSWAP_TOOLS = [
    FunctionTool(set_model),
    FunctionTool(set_prompt),
    FunctionTool(get_config),
]


__all__ = [
    "set_model",
    "set_prompt",
    "get_config",
    "HOTSWAP_TOOLS",
]
