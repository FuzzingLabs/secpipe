#!/usr/bin/env python3
"""Minimal A2A client utility for hot-swapping LiteLLM model/prompt."""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional
from uuid import uuid4

import httpx
from a2a.client import A2AClient
from a2a.client.errors import A2AClientHTTPError
from a2a.types import (
    JSONRPCErrorResponse,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TextPart,
)

from litellm_agent.control import (
    HotSwapCommand,
    build_control_message,
    parse_model_spec,
    serialize_model_spec,
)

DEFAULT_URL = "http://localhost:8000/a2a/litellm_agent"


async def _collect_text(client: A2AClient, message: str, context_id: str) -> str:
    """Send a message and collect streamed agent text into a single string."""

    params = MessageSendParams(
        configuration=MessageSendConfiguration(blocking=True),
        message=Message(
            context_id=context_id,
            message_id=str(uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
        ),
    )

    stream_request = SendStreamingMessageRequest(id=str(uuid4()), params=params)
    buffer: list[str] = []
    try:
        async for response in client.send_message_streaming(stream_request):
            root = response.root
            if isinstance(root, JSONRPCErrorResponse):
                raise RuntimeError(f"A2A error: {root.error}")

            payload = root.result
            buffer.extend(_extract_text(payload))
    except A2AClientHTTPError as exc:
        if "text/event-stream" not in str(exc):
            raise

        send_request = SendMessageRequest(id=str(uuid4()), params=params)
        response = await client.send_message(send_request)
        root = response.root
        if isinstance(root, JSONRPCErrorResponse):
            raise RuntimeError(f"A2A error: {root.error}")
        payload = root.result
        buffer.extend(_extract_text(payload))

    if buffer:
        buffer = list(dict.fromkeys(buffer))
    return "\n".join(buffer).strip()


def _extract_text(
    result: Message | Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent,
) -> list[str]:
    texts: list[str] = []
    if isinstance(result, Message):
        if result.role is Role.agent:
            for part in result.parts:
                root_part = part.root
                text = getattr(root_part, "text", None)
                if text:
                    texts.append(text)
    elif isinstance(result, Task) and result.history:
        for msg in result.history:
            if msg.role is Role.agent:
                for part in msg.parts:
                    root_part = part.root
                    text = getattr(root_part, "text", None)
                    if text:
                        texts.append(text)
    elif isinstance(result, TaskStatusUpdateEvent):
        message = result.status.message
        if message:
            texts.extend(_extract_text(message))
    elif isinstance(result, TaskArtifactUpdateEvent):
        artifact = result.artifact
        if artifact and artifact.parts:
            for part in artifact.parts:
                root_part = part.root
                text = getattr(root_part, "text", None)
                if text:
                    texts.append(text)
    return texts


def _split_model_args(model_args: Optional[list[str]]) -> tuple[Optional[str], Optional[str]]:
    if not model_args:
        return None, None

    if len(model_args) == 1:
        return model_args[0], None

    provider = model_args[0]
    model = " ".join(model_args[1:])
    return model, provider


async def hot_swap(
    url: str,
    *,
    model_args: Optional[list[str]],
    provider: Optional[str],
    prompt: Optional[str],
    message: Optional[str],
    show_config: bool,
    context_id: Optional[str],
    timeout: float,
) -> None:
    """Execute the requested hot-swap operations against the A2A endpoint."""

    timeout_config = httpx.Timeout(timeout)
    async with httpx.AsyncClient(timeout=timeout_config) as http_client:
        client = A2AClient(url=url, httpx_client=http_client)
        session_id = context_id or str(uuid4())

        model, derived_provider = _split_model_args(model_args)

        if model:
            spec = parse_model_spec(model, provider=provider or derived_provider)
            payload = serialize_model_spec(spec)
            control_msg = build_control_message(HotSwapCommand.MODEL, payload)
            result = await _collect_text(client, control_msg, session_id)
            print(f"Model response: {result or '(no response)'}")

        if prompt is not None:
            control_msg = build_control_message(HotSwapCommand.PROMPT, prompt)
            result = await _collect_text(client, control_msg, session_id)
            print(f"Prompt response: {result or '(no response)'}")

        if show_config:
            control_msg = build_control_message(HotSwapCommand.GET_CONFIG)
            result = await _collect_text(client, control_msg, session_id)
            print(f"Config:\n{result or '(no response)'}")

        if message:
            result = await _collect_text(client, message, session_id)
            print(f"Message response: {result or '(no response)'}")

        print(f"Context ID: {session_id}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"A2A endpoint for the agent (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--model",
        nargs="+",
        help="LiteLLM model spec: either 'provider/model' or '<provider> <model>'.",
    )
    parser.add_argument(
        "--provider",
        help="Optional LiteLLM provider when --model lacks a prefix.")
    parser.add_argument(
        "--prompt",
        help="Set the system prompt (omit to leave unchanged; empty string clears it).",
    )
    parser.add_argument(
        "--message",
        help="Send an additional user message after the swaps complete.")
    parser.add_argument(
        "--config",
        action="store_true",
        help="Print the agent configuration after performing swaps.")
    parser.add_argument(
        "--context",
        help="Optional context/session identifier to reuse across calls.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout (seconds) for A2A calls (default: 60).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        hot_swap(
            args.url,
            model_args=args.model,
            provider=args.provider,
            prompt=args.prompt,
            message=args.message,
            show_config=args.config,
            context_id=args.context,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
