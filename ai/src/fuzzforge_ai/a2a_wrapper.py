"""
A2A Wrapper Module for FuzzForge
Programmatic interface to send tasks to A2A agents with custom model/prompt/context
"""
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

from __future__ import annotations

from typing import Optional, Any
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


class A2ATaskResult:
    """Result from an A2A agent task"""

    def __init__(self, text: str, context_id: str, raw_response: Any = None):
        self.text = text
        self.context_id = context_id
        self.raw_response = raw_response

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"A2ATaskResult(text={self.text[:50]}..., context_id={self.context_id})"


def _build_control_message(command: str, payload: Optional[str] = None) -> str:
    """Build a control message for hot-swapping agent configuration"""
    if payload is None or payload == "":
        return f"[HOTSWAP:{command}]"
    return f"[HOTSWAP:{command}:{payload}]"


def _extract_text(
    result: Message | Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent,
) -> list[str]:
    """Extract text content from A2A response objects"""
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


async def _send_message(
    client: A2AClient,
    message: str,
    context_id: str,
) -> str:
    """Send a message to the A2A agent and collect the response"""

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

        # Fallback to non-streaming
        send_request = SendMessageRequest(id=str(uuid4()), params=params)
        response = await client.send_message(send_request)
        root = response.root
        if isinstance(root, JSONRPCErrorResponse):
            raise RuntimeError(f"A2A error: {root.error}")
        payload = root.result
        buffer.extend(_extract_text(payload))

    if buffer:
        buffer = list(dict.fromkeys(buffer))  # Remove duplicates
    return "\n".join(buffer).strip()


async def send_agent_task(
    url: str,
    message: str,
    *,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    prompt: Optional[str] = None,
    context: Optional[str] = None,
    timeout: float = 120.0,
) -> A2ATaskResult:
    """
    Send a task to an A2A agent with optional model/prompt configuration.

    Args:
        url: A2A endpoint URL (e.g., "http://127.0.0.1:8000/a2a/litellm_agent")
        message: The task message to send to the agent
        model: Optional model name (e.g., "gpt-4o", "gemini-2.0-flash")
        provider: Optional provider name (e.g., "openai", "gemini")
        prompt: Optional system prompt to set before sending the message
        context: Optional context/session ID (generated if not provided)
        timeout: Request timeout in seconds (default: 120)

    Returns:
        A2ATaskResult with the agent's response text and context ID

    Example:
        >>> result = await send_agent_task(
        ...     url="http://127.0.0.1:8000/a2a/litellm_agent",
        ...     model="gpt-4o",
        ...     provider="openai",
        ...     prompt="You are concise.",
        ...     message="Give me a fuzzing harness.",
        ...     context="fuzzing",
        ...     timeout=120
        ... )
        >>> print(result.text)
    """
    timeout_config = httpx.Timeout(timeout)
    context_id = context or str(uuid4())

    async with httpx.AsyncClient(timeout=timeout_config) as http_client:
        client = A2AClient(url=url, httpx_client=http_client)

        # Set model if provided
        if model:
            model_spec = f"{provider}/{model}" if provider else model
            control_msg = _build_control_message("MODEL", model_spec)
            await _send_message(client, control_msg, context_id)

        # Set prompt if provided
        if prompt is not None:
            control_msg = _build_control_message("PROMPT", prompt)
            await _send_message(client, control_msg, context_id)

        # Send the actual task message
        response_text = await _send_message(client, message, context_id)

        return A2ATaskResult(
            text=response_text,
            context_id=context_id,
        )


async def get_agent_config(
    url: str,
    context: Optional[str] = None,
    timeout: float = 60.0,
) -> str:
    """
    Get the current configuration of an A2A agent.

    Args:
        url: A2A endpoint URL
        context: Optional context/session ID
        timeout: Request timeout in seconds

    Returns:
        Configuration string from the agent
    """
    timeout_config = httpx.Timeout(timeout)
    context_id = context or str(uuid4())

    async with httpx.AsyncClient(timeout=timeout_config) as http_client:
        client = A2AClient(url=url, httpx_client=http_client)
        control_msg = _build_control_message("GET_CONFIG")
        config_text = await _send_message(client, control_msg, context_id)
        return config_text


async def hot_swap_model(
    url: str,
    model: str,
    provider: Optional[str] = None,
    context: Optional[str] = None,
    timeout: float = 60.0,
) -> str:
    """
    Hot-swap the model of an A2A agent without sending a task.

    Args:
        url: A2A endpoint URL
        model: Model name to switch to
        provider: Optional provider name
        context: Optional context/session ID
        timeout: Request timeout in seconds

    Returns:
        Response from the agent
    """
    timeout_config = httpx.Timeout(timeout)
    context_id = context or str(uuid4())

    async with httpx.AsyncClient(timeout=timeout_config) as http_client:
        client = A2AClient(url=url, httpx_client=http_client)
        model_spec = f"{provider}/{model}" if provider else model
        control_msg = _build_control_message("MODEL", model_spec)
        response = await _send_message(client, control_msg, context_id)
        return response


async def hot_swap_prompt(
    url: str,
    prompt: str,
    context: Optional[str] = None,
    timeout: float = 60.0,
) -> str:
    """
    Hot-swap the system prompt of an A2A agent.

    Args:
        url: A2A endpoint URL
        prompt: System prompt to set
        context: Optional context/session ID
        timeout: Request timeout in seconds

    Returns:
        Response from the agent
    """
    timeout_config = httpx.Timeout(timeout)
    context_id = context or str(uuid4())

    async with httpx.AsyncClient(timeout=timeout_config) as http_client:
        client = A2AClient(url=url, httpx_client=http_client)
        control_msg = _build_control_message("PROMPT", prompt)
        response = await _send_message(client, control_msg, context_id)
        return response
