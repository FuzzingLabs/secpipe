"""Callbacks and instruction providers for the LiteLLM hot-swap agent."""

from __future__ import annotations

import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from .config import CONTROL_PREFIX, DEFAULT_MODEL
from .control import HotSwapCommand, parse_control_message, parse_model_spec
from .prompts import BASE_INSTRUCTION
from .state import HotSwapState, apply_state_to_agent

_LOGGER = logging.getLogger(__name__)


def provide_instruction(ctx: ReadonlyContext | None = None) -> str:
    """Compose the system instruction using the stored state."""

    state_mapping = getattr(ctx, "state", None)
    state = HotSwapState.from_mapping(state_mapping)
    prompt = state.prompt or BASE_INSTRUCTION
    return f"{prompt}\n\nActive model: {state.display_model}"


def _ensure_state(callback_context: CallbackContext) -> HotSwapState:
    state = HotSwapState.from_mapping(callback_context.state)
    state.persist(callback_context.state)
    return state


def _session_id(callback_context: CallbackContext) -> str:
    session = getattr(callback_context, "session", None)
    if session is None:
        session = getattr(callback_context._invocation_context, "session", None)
    return getattr(session, "id", "unknown-session")


async def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[types.Content]:
    """Ensure outgoing requests use the active model from session state."""

    state = _ensure_state(callback_context)
    try:
        apply_state_to_agent(callback_context._invocation_context, state)
    except Exception:  # pragma: no cover - defensive logging
        _LOGGER.exception(
            "Failed to apply LiteLLM model '%s' (provider=%s) for session %s",
            state.model,
            state.provider,
            callback_context.session.id,
        )
    llm_request.model = state.model or DEFAULT_MODEL
    return None


async def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """Intercept hot-swap control messages and update session state."""

    user_content = callback_context.user_content
    if not user_content or not user_content.parts:
        return None

    first_part = user_content.parts[0]
    message_text = (first_part.text or "").strip()
    if not message_text.startswith(CONTROL_PREFIX):
        return None

    parsed = parse_control_message(message_text)
    if not parsed:
        return None

    command, payload = parsed
    state = _ensure_state(callback_context)

    if command is HotSwapCommand.MODEL:
        if not payload:
            return _render("❌ Missing model specification for hot-swap.")
        try:
            spec = parse_model_spec(payload)
        except ValueError as exc:
            return _render(f"❌ Invalid model specification: {exc}")

        state.model = spec.model
        state.provider = spec.provider
        state.persist(callback_context.state)
        try:
            apply_state_to_agent(callback_context._invocation_context, state)
        except Exception:  # pragma: no cover - defensive logging
            _LOGGER.exception(
                "Failed to apply LiteLLM model '%s' (provider=%s) for session %s",
                state.model,
                state.provider,
                _session_id(callback_context),
            )
        _LOGGER.info(
            "Hot-swapped model to %s (provider=%s, session=%s)",
            state.model,
            state.provider,
            _session_id(callback_context),
        )
        label = state.display_model
        return _render(f"✅ Model switched to: {label}")

    if command is HotSwapCommand.PROMPT:
        prompt_value = (payload or "").strip()
        state.prompt = prompt_value or None
        state.persist(callback_context.state)
        if state.prompt:
            _LOGGER.info(
                "Updated prompt for session %s", _session_id(callback_context)
            )
            return _render(
                "✅ System prompt updated. This change takes effect immediately."
            )
        return _render("✅ System prompt cleared. Reverting to default instruction.")

    if command is HotSwapCommand.GET_CONFIG:
        return _render(state.describe())

    expected = ", ".join(HotSwapCommand.choices())
    return _render(
        "⚠️ Unsupported hot-swap command. Available verbs: "
        f"{expected}."
    )


def _render(message: str) -> types.ModelContent:
    return types.ModelContent(parts=[types.Part(text=message)])
