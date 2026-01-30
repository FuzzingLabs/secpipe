"""Root agent definition for the LiteLLM hot-swap shell."""

from __future__ import annotations

from google.adk.agents import Agent

from .callbacks import (
    before_agent_callback,
    before_model_callback,
    provide_instruction,
)
from .config import AGENT_DESCRIPTION, AGENT_NAME, DEFAULT_MODEL, DEFAULT_PROVIDER
from .state import HotSwapState
from .tools import HOTSWAP_TOOLS

_initial_state = HotSwapState(model=DEFAULT_MODEL, provider=DEFAULT_PROVIDER)

root_agent = Agent(
    name=AGENT_NAME,
    model=_initial_state.instantiate_llm(),
    description=AGENT_DESCRIPTION,
    instruction=provide_instruction,
    tools=HOTSWAP_TOOLS,
    before_agent_callback=before_agent_callback,
    before_model_callback=before_model_callback,
)


__all__ = ["root_agent"]
