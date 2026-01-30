"""Control message helpers for hot-swapping model and prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .config import DEFAULT_PROVIDER


class HotSwapCommand(str, Enum):
    """Supported control verbs embedded in user messages."""

    MODEL = "MODEL"
    PROMPT = "PROMPT"
    GET_CONFIG = "GET_CONFIG"

    @classmethod
    def choices(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


@dataclass(frozen=True)
class ModelSpec:
    """Represents a LiteLLM model and optional provider."""

    model: str
    provider: Optional[str] = None


_COMMAND_PATTERN = re.compile(
    r"^\[HOTSWAP:(?P<verb>[A-Z_]+)(?::(?P<payload>.*))?\]$",
)


def parse_control_message(text: str) -> Optional[Tuple[HotSwapCommand, Optional[str]]]:
    """Return hot-swap command tuple when the string matches the control format."""

    match = _COMMAND_PATTERN.match(text.strip())
    if not match:
        return None

    verb = match.group("verb")
    if verb not in HotSwapCommand.choices():
        return None

    payload = match.group("payload")
    return HotSwapCommand(verb), payload if payload else None


def build_control_message(command: HotSwapCommand, payload: Optional[str] = None) -> str:
    """Serialise a control command for downstream clients."""

    if command not in HotSwapCommand:
        raise ValueError(f"Unsupported hot-swap command: {command}")
    if payload is None or payload == "":
        return f"[HOTSWAP:{command.value}]"
    return f"[HOTSWAP:{command.value}:{payload}]"


def parse_model_spec(model: str, provider: Optional[str] = None) -> ModelSpec:
    """Parse model/provider inputs into a structured ModelSpec."""

    candidate = (model or "").strip()
    if not candidate:
        raise ValueError("Model name cannot be empty")

    if provider:
        provider_clean = provider.strip()
        if not provider_clean:
            raise ValueError("Provider cannot be empty when supplied")
        if "/" in candidate:
            raise ValueError(
                "Provide either provider/model or use provider argument, not both",
            )
        return ModelSpec(model=candidate, provider=provider_clean)

    if "/" in candidate:
        provider_part, model_part = candidate.split("/", 1)
        provider_part = provider_part.strip()
        model_part = model_part.strip()
        if not provider_part or not model_part:
            raise ValueError("Model spec must include provider and model when using '/' format")
        return ModelSpec(model=model_part, provider=provider_part)

    if DEFAULT_PROVIDER:
        return ModelSpec(model=candidate, provider=DEFAULT_PROVIDER.strip())

    return ModelSpec(model=candidate, provider=None)


def serialize_model_spec(spec: ModelSpec) -> str:
    """Render a ModelSpec to provider/model string for control messages."""

    if spec.provider:
        return f"{spec.provider}/{spec.model}"
    return spec.model
