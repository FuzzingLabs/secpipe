"""MCP client for communicating with hub servers.

This module provides a generic MCP client that can connect to any MCP server
via stdio (docker/command) or SSE transport. It handles:
- Starting containers/processes for stdio transport
- Connecting to SSE endpoints
- Discovering tools via list_tools()
- Executing tools via call_tool()
- Persistent container sessions for stateful interactions

"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from secpipe_common.hub.models import (
    HubServer,
    HubServerConfig,
    HubServerType,
    HubTool,
)

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import AsyncGenerator

    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


class HubClientError(Exception):
    """Error in hub client operations."""


@dataclass
class PersistentSession:
    """A persistent container session with an active MCP connection.

    Keeps a Docker container running between tool calls to allow
    stateful interactions (e.g., radare2 analysis, long-running fuzzing).

    """

    #: Server name this session belongs to.
    server_name: str

    #: Docker container name.
    container_name: str

    #: Underlying process (docker run).
    process: Process

    #: Stream reader (process stdout).
    reader: asyncio.StreamReader

    #: Stream writer (process stdin).
    writer: asyncio.StreamWriter

    #: Whether the MCP session has been initialized.
    initialized: bool = False

    #: Lock to serialise concurrent requests on the same session.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    #: When the session was started.
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    #: Monotonic counter for JSON-RPC request IDs.
    request_id: int = 0

    @property
    def alive(self) -> bool:
        """Check if the underlying process is still running."""
        return self.process.returncode is None


class HubClient:
    """Client for communicating with MCP hub servers.

    Supports stdio (via docker/command) and SSE transports.
    Uses the MCP protocol for tool discovery and execution.

    """

    #: Default timeout for operations.
    DEFAULT_TIMEOUT: int = 30

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize the hub client.

        :param timeout: Default timeout for operations in seconds.

        """
        self._timeout = timeout
        self._persistent_sessions: dict[str, PersistentSession] = {}
        self._request_id: int = 0

    async def discover_tools(self, server: HubServer) -> list[HubTool]:
        """Discover tools from a hub server.

        Connects to the server, calls list_tools(), and returns
        parsed HubTool instances.

        :param server: Hub server to discover tools from.
        :returns: List of discovered tools.
        :raises HubClientError: If discovery fails.

        """
        logger = get_logger()
        config = server.config

        logger.info("Discovering tools", server=config.name, type=config.type.value)

        try:
            async with self._connect(config) as (reader, writer):
                # Initialise MCP session (skip for persistent — already done)
                if not self._persistent_sessions.get(config.name):
                    await self._initialize_session(reader, writer, config.name)

                # List tools
                tools_data = await self._call_method(
                    reader,
                    writer,
                    "tools/list",
                    {},
                )

                # Parse tools
                tools = []
                for tool_data in tools_data.get("tools", []):
                    tool = HubTool.from_mcp_tool(
                        server_name=config.name,
                        name=tool_data["name"],
                        description=tool_data.get("description"),
                        input_schema=tool_data.get("inputSchema", {}),
                    )
                    tools.append(tool)

                logger.info(
                    "Discovered tools",
                    server=config.name,
                    count=len(tools),
                )
                return tools

        except Exception as e:
            logger.error(
                "Tool discovery failed",
                server=config.name,
                error=str(e),
            )
            raise HubClientError(f"Discovery failed for {config.name}: {e}") from e

    async def execute_tool(
        self,
        server: HubServer,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        timeout: int | None = None,
        extra_volumes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool on a hub server.

        :param server: Hub server to execute on.
        :param tool_name: Name of the tool to execute.
        :param arguments: Tool arguments.
        :param timeout: Execution timeout (uses default if None).
        :param extra_volumes: Additional Docker volume mounts to inject.
        :returns: Tool execution result.
        :raises HubClientError: If execution fails.

        """
        logger = get_logger()
        config = server.config
        exec_timeout = timeout or config.timeout or self._timeout

        logger.info(
            "Executing hub tool",
            server=config.name,
            tool=tool_name,
            timeout=exec_timeout,
        )

        try:
            async with self._connect(config, extra_volumes=extra_volumes) as (reader, writer):
                # Initialise MCP session (skip for persistent — already done)
                if not self._persistent_sessions.get(config.name):
                    await self._initialize_session(reader, writer, config.name)

                # Call tool
                result = await asyncio.wait_for(
                    self._call_method(
                        reader,
                        writer,
                        "tools/call",
                        {"name": tool_name, "arguments": arguments},
                    ),
                    timeout=exec_timeout,
                )

                logger.info(
                    "Tool execution completed",
                    server=config.name,
                    tool=tool_name,
                )
                return result

        except asyncio.TimeoutError as e:
            logger.error(
                "Tool execution timed out",
                server=config.name,
                tool=tool_name,
                timeout=exec_timeout,
            )
            raise HubClientError(
                f"Execution timed out for {config.name}:{tool_name}"
            ) from e

        except Exception as e:
            logger.error(
                "Tool execution failed",
                server=config.name,
                tool=tool_name,
                error=str(e),
            )
            raise HubClientError(
                f"Execution failed for {config.name}:{tool_name}: {e}"
            ) from e

    @asynccontextmanager
    async def _connect(
        self,
        config: HubServerConfig,
        extra_volumes: list[str] | None = None,
    ) -> AsyncGenerator[tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """Connect to an MCP server.

        If a persistent session exists for this server, reuse it (with a lock
        to serialise concurrent requests). Otherwise, fall through to the
        ephemeral per-call connection logic.

        :param config: Server configuration.
        :param extra_volumes: Additional Docker volume mounts to inject.
        :yields: Tuple of (reader, writer) for communication.

        """
        # Check for active persistent session
        session = self._persistent_sessions.get(config.name)
        if session and session.initialized and session.alive:
            async with session.lock:
                yield session.reader, session.writer  # type: ignore[misc]
            return

        # Ephemeral connection (original behaviour)
        if config.type == HubServerType.DOCKER:
            async with self._connect_docker(config, extra_volumes=extra_volumes) as streams:
                yield streams
        elif config.type == HubServerType.COMMAND:
            async with self._connect_command(config) as streams:
                yield streams
        elif config.type == HubServerType.SSE:
            async with self._connect_sse(config) as streams:
                yield streams
        else:
            msg = f"Unsupported server type: {config.type}"
            raise HubClientError(msg)

    @asynccontextmanager
    async def _connect_docker(
        self,
        config: HubServerConfig,
        extra_volumes: list[str] | None = None,
    ) -> AsyncGenerator[tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """Connect to a Docker-based MCP server.

        :param config: Server configuration with image name.
        :param extra_volumes: Additional volume mounts to inject (e.g. project assets).
        :yields: Tuple of (reader, writer) for stdio communication.

        """
        if not config.image:
            msg = f"Docker image not specified for server '{config.name}'"
            raise HubClientError(msg)

        # Build docker command
        cmd = ["docker", "run", "-i", "--rm"]

        # Add capabilities
        for cap in config.capabilities:
            cmd.extend(["--cap-add", cap])

        # Add volumes from server config
        for volume in config.volumes:
            cmd.extend(["-v", os.path.expanduser(volume)])

        # Add extra volumes (e.g. project assets injected at runtime)
        for volume in (extra_volumes or []):
            cmd.extend(["-v", os.path.expanduser(volume)])

        # Add environment variables
        for key, value in config.environment.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(config.image)

        # Use 4 MB buffer to handle large tool responses (YARA rulesets, trivy output, etc.)
        _STREAM_LIMIT = 4 * 1024 * 1024

        process: Process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            limit=_STREAM_LIMIT,
        )

        try:
            if process.stdin is None or process.stdout is None:
                msg = "Failed to get process streams"
                raise HubClientError(msg)

            # Create asyncio streams from process pipes
            reader = process.stdout
            writer = process.stdin

            yield reader, writer  # type: ignore[misc]

        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()

    @asynccontextmanager
    async def _connect_command(
        self,
        config: HubServerConfig,
    ) -> AsyncGenerator[tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """Connect to a command-based MCP server.

        :param config: Server configuration with command.
        :yields: Tuple of (reader, writer) for stdio communication.

        """
        if not config.command:
            msg = f"Command not specified for server '{config.name}'"
            raise HubClientError(msg)

        # Set up environment
        env = dict(config.environment) if config.environment else None

        # Use 4 MB buffer to handle large tool responses
        _STREAM_LIMIT = 4 * 1024 * 1024

        process: Process = await asyncio.create_subprocess_exec(
            *config.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            limit=_STREAM_LIMIT,
        )

        try:
            if process.stdin is None or process.stdout is None:
                msg = "Failed to get process streams"
                raise HubClientError(msg)

            reader = process.stdout
            writer = process.stdin

            yield reader, writer  # type: ignore[misc]

        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()

    @asynccontextmanager
    async def _connect_sse(
        self,
        config: HubServerConfig,
    ) -> AsyncGenerator[tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """Connect to an SSE-based MCP server.

        :param config: Server configuration with URL.
        :yields: Tuple of (reader, writer) for SSE communication.

        """
        # SSE support requires additional dependencies
        # For now, raise not implemented
        msg = "SSE transport not yet implemented"
        raise NotImplementedError(msg)

    async def _initialize_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        server_name: str,
    ) -> dict[str, Any]:
        """Initialize MCP session with the server.

        :param reader: Stream reader.
        :param writer: Stream writer.
        :param server_name: Server name for logging.
        :returns: Server capabilities.

        """
        # Send initialize request
        result = await self._call_method(
            reader,
            writer,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "secpipe-hub",
                    "version": "0.1.0",
                },
            },
        )

        # Send initialized notification
        await self._send_notification(reader, writer, "notifications/initialized", {})

        return result

    async def _call_method(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Call an MCP method.

        :param reader: Stream reader.
        :param writer: Stream writer.
        :param method: Method name.
        :param params: Method parameters.
        :returns: Method result.

        """
        # Create JSON-RPC request with unique ID
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        # Send request
        request_line = json.dumps(request) + "\n"
        writer.write(request_line.encode())
        await writer.drain()

        # Read response
        response_line = await asyncio.wait_for(
            reader.readline(),
            timeout=self._timeout,
        )

        if not response_line:
            msg = "Empty response from server"
            raise HubClientError(msg)

        response = json.loads(response_line.decode())

        if "error" in response:
            error = response["error"]
            msg = f"MCP error: {error.get('message', 'Unknown error')}"
            raise HubClientError(msg)

        result = response.get("result", {})

        # Check for tool-level errors in content items
        for item in result.get("content", []):
            if item.get("isError", False):
                error_text = item.get("text", "unknown error")
                msg = f"Tool returned error: {error_text}"
                raise HubClientError(msg)

        return result

    async def _send_notification(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        method: str,
        params: dict[str, Any],
    ) -> None:
        """Send an MCP notification (no response expected).

        :param reader: Stream reader (unused but kept for consistency).
        :param writer: Stream writer.
        :param method: Notification method name.
        :param params: Notification parameters.

        """
        # Create JSON-RPC notification (no id)
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        notification_line = json.dumps(notification) + "\n"
        writer.write(notification_line.encode())
        await writer.drain()

    # ------------------------------------------------------------------
    # Persistent session management
    # ------------------------------------------------------------------

    async def start_persistent_session(
        self,
        config: HubServerConfig,
        extra_volumes: list[str] | None = None,
    ) -> PersistentSession:
        """Start a persistent Docker container and initialise MCP session.

        The container stays running until :meth:`stop_persistent_session` is
        called, allowing multiple tool calls on the same session.

        :param config: Server configuration (must be Docker type).
        :param extra_volumes: Additional host:container volume mounts to inject.
        :returns: The created persistent session.
        :raises HubClientError: If the container cannot be started.

        """
        logger = get_logger()

        if config.name in self._persistent_sessions:
            session = self._persistent_sessions[config.name]
            if session.alive:
                logger.info("Persistent session already running", server=config.name)
                return session
            # Dead session — clean up and restart
            await self._cleanup_session(config.name)

        if config.type != HubServerType.DOCKER:
            msg = f"Persistent mode only supports Docker servers (got {config.type.value})"
            raise HubClientError(msg)

        if not config.image:
            msg = f"Docker image not specified for server '{config.name}'"
            raise HubClientError(msg)

        container_name = f"secpipe-{config.name}"

        # Remove stale container with same name if it exists
        try:
            rm_proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", container_name,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await rm_proc.wait()
        except Exception:
            pass

        # Build docker run command (no --rm, with --name)
        cmd = ["docker", "run", "-i", "--name", container_name]

        for cap in config.capabilities:
            cmd.extend(["--cap-add", cap])

        for volume in config.volumes:
            cmd.extend(["-v", os.path.expanduser(volume)])

        for extra_vol in (extra_volumes or []):
            cmd.extend(["-v", extra_vol])

        for key, value in config.environment.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(config.image)

        _STREAM_LIMIT = 4 * 1024 * 1024

        logger.info(
            "Starting persistent container",
            server=config.name,
            container=container_name,
            image=config.image,
        )

        process: Process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            limit=_STREAM_LIMIT,
        )

        if process.stdin is None or process.stdout is None:
            process.terminate()
            msg = "Failed to get process streams"
            raise HubClientError(msg)

        session = PersistentSession(
            server_name=config.name,
            container_name=container_name,
            process=process,
            reader=process.stdout,
            writer=process.stdin,
        )

        # Initialise MCP session
        try:
            await self._initialize_session(
                session.reader,  # type: ignore[arg-type]
                session.writer,  # type: ignore[arg-type]
                config.name,
            )
            session.initialized = True
        except Exception as e:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
            msg = f"Failed to initialise MCP session for {config.name}: {e}"
            raise HubClientError(msg) from e

        self._persistent_sessions[config.name] = session

        logger.info(
            "Persistent session started",
            server=config.name,
            container=container_name,
        )
        return session

    async def stop_persistent_session(self, server_name: str) -> bool:
        """Stop a persistent container session.

        :param server_name: Name of the server whose session to stop.
        :returns: True if a session was stopped, False if none found.

        """
        return await self._cleanup_session(server_name)

    def get_persistent_session(self, server_name: str) -> PersistentSession | None:
        """Get a persistent session by server name.

        :param server_name: Server name.
        :returns: The session if running, None otherwise.

        """
        session = self._persistent_sessions.get(server_name)
        if session and not session.alive:
            # Mark dead session — don't remove here to avoid async issues
            return None
        return session

    def list_persistent_sessions(self) -> list[dict[str, Any]]:
        """List all persistent sessions with their status.

        :returns: List of session info dictionaries.

        """
        sessions = []
        for name, session in self._persistent_sessions.items():
            sessions.append({
                "server_name": name,
                "container_name": session.container_name,
                "alive": session.alive,
                "initialized": session.initialized,
                "started_at": session.started_at.isoformat(),
                "uptime_seconds": int(
                    (datetime.now(tz=timezone.utc) - session.started_at).total_seconds()
                ),
            })
        return sessions

    async def stop_all_persistent_sessions(self) -> int:
        """Stop all persistent sessions.

        :returns: Number of sessions stopped.

        """
        names = list(self._persistent_sessions.keys())
        count = 0
        for name in names:
            if await self._cleanup_session(name):
                count += 1
        return count

    async def _cleanup_session(self, server_name: str) -> bool:
        """Clean up a persistent session (terminate process, remove container).

        :param server_name: Server name.
        :returns: True if cleaned up, False if not found.

        """
        logger = get_logger()
        session = self._persistent_sessions.pop(server_name, None)
        if session is None:
            return False

        logger.info("Stopping persistent session", server=server_name)

        # Terminate process
        if session.alive:
            session.process.terminate()
            try:
                await asyncio.wait_for(session.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                session.process.kill()
                await session.process.wait()

        # Remove Docker container
        try:
            rm_proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", session.container_name,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await rm_proc.wait()
        except Exception:
            pass

        logger.info(
            "Persistent session stopped",
            server=server_name,
            container=session.container_name,
        )
        return True
