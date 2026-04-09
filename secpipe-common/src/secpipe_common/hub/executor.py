"""Hub executor for managing MCP server lifecycle and tool execution.

This module provides a high-level interface for:
- Discovering tools from all registered hub servers
- Executing tools with proper error handling
- Managing the lifecycle of hub operations

"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from secpipe_common.hub.client import HubClient, HubClientError, PersistentSession
from secpipe_common.hub.models import HubServer, HubServerConfig, HubTool
from secpipe_common.hub.registry import HubRegistry

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


class HubExecutionResult:
    """Result of a hub tool execution."""

    def __init__(
        self,
        *,
        success: bool,
        server_name: str,
        tool_name: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Initialize execution result.

        :param success: Whether execution succeeded.
        :param server_name: Name of the hub server.
        :param tool_name: Name of the executed tool.
        :param result: Tool execution result data.
        :param error: Error message if execution failed.

        """
        self.success = success
        self.server_name = server_name
        self.tool_name = tool_name
        self.result = result or {}
        self.error = error

    @property
    def identifier(self) -> str:
        """Get full tool identifier."""
        return f"hub:{self.server_name}:{self.tool_name}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        :returns: Dictionary representation.

        """
        return {
            "success": self.success,
            "identifier": self.identifier,
            "server": self.server_name,
            "tool": self.tool_name,
            "result": self.result,
            "error": self.error,
        }


class HubExecutor:
    """Executor for hub server operations.

    Provides high-level methods for discovering and executing
    tools from hub servers.

    """

    #: Hub registry instance.
    _registry: HubRegistry

    #: MCP client instance.
    _client: HubClient

    def __init__(
        self,
        config_path: Path | None = None,
        timeout: int = 300,
    ) -> None:
        """Initialize the hub executor.

        :param config_path: Path to hub-servers.json config file.
        :param timeout: Default timeout for tool execution.

        """
        self._registry = HubRegistry(config_path)
        self._client = HubClient(timeout=timeout)
        self._continuous_sessions: dict[str, dict[str, Any]] = {}

    @property
    def registry(self) -> HubRegistry:
        """Get the hub registry.

        :returns: Hub registry instance.

        """
        return self._registry

    def add_server(self, config: HubServerConfig) -> HubServer:
        """Add a server to the registry.

        :param config: Server configuration.
        :returns: Created HubServer instance.

        """
        return self._registry.add_server(config)

    async def discover_all_tools(self) -> dict[str, list[HubTool]]:
        """Discover tools from all enabled servers.

        :returns: Dict mapping server names to lists of discovered tools.

        """
        logger = get_logger()
        results: dict[str, list[HubTool]] = {}

        for server in self._registry.enabled_servers:
            try:
                tools = await self._client.discover_tools(server)
                self._registry.update_server_tools(server.name, tools)
                results[server.name] = tools

            except HubClientError as e:
                logger.warning(
                    "Failed to discover tools",
                    server=server.name,
                    error=str(e),
                )
                self._registry.update_server_tools(server.name, [], error=str(e))
                results[server.name] = []

        return results

    async def discover_server_tools(self, server_name: str) -> list[HubTool]:
        """Discover tools from a specific server.

        :param server_name: Name of the server.
        :returns: List of discovered tools.
        :raises ValueError: If server not found.

        """
        server = self._registry.get_server(server_name)
        if not server:
            msg = f"Server '{server_name}' not found"
            raise ValueError(msg)

        try:
            tools = await self._client.discover_tools(server)
            self._registry.update_server_tools(server_name, tools)
            return tools

        except HubClientError as e:
            self._registry.update_server_tools(server_name, [], error=str(e))
            raise

    async def execute_tool(
        self,
        identifier: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: int | None = None,
        extra_volumes: list[str] | None = None,
    ) -> HubExecutionResult:
        """Execute a hub tool.

        :param identifier: Tool identifier (hub:server:tool or server:tool).
        :param arguments: Tool arguments.
        :param timeout: Execution timeout.
        :param extra_volumes: Additional Docker volume mounts to inject.
        :returns: Execution result.

        """
        logger = get_logger()
        arguments = arguments or {}

        # Parse identifier and find tool
        server, tool = self._registry.find_tool(identifier)

        if not server or not tool:
            # Try to parse as server:tool and discover
            parts = identifier.replace("hub:", "").split(":")
            if len(parts) == 2:  # noqa: PLR2004
                server_name, tool_name = parts
                server = self._registry.get_server(server_name)

                if server and not server.discovered:
                    # Try to discover tools first
                    try:
                        await self.discover_server_tools(server_name)
                        tool = server.get_tool(tool_name)
                    except HubClientError:
                        pass

                if server and not tool:
                    # Tool not found, but server exists - try to execute anyway
                    # The server might have the tool even if discovery failed
                    tool_name_to_use = tool_name
                else:
                    tool_name_to_use = tool.name if tool else ""

                if not server:
                    return HubExecutionResult(
                        success=False,
                        server_name=server_name,
                        tool_name=tool_name,
                        error=f"Server '{server_name}' not found",
                    )

                # Execute even if tool wasn't discovered (server might still have it)
                try:
                    result = await self._client.execute_tool(
                        server,
                        tool_name_to_use or tool_name,
                        arguments,
                        timeout=timeout,
                        extra_volumes=extra_volumes,
                    )
                    return HubExecutionResult(
                        success=True,
                        server_name=server.name,
                        tool_name=tool_name_to_use or tool_name,
                        result=result,
                    )
                except HubClientError as e:
                    return HubExecutionResult(
                        success=False,
                        server_name=server.name,
                        tool_name=tool_name_to_use or tool_name,
                        error=str(e),
                    )
            else:
                return HubExecutionResult(
                    success=False,
                    server_name="unknown",
                    tool_name=identifier,
                    error=f"Invalid tool identifier: {identifier}",
                )

        # Execute the tool
        logger.info(
            "Executing hub tool",
            server=server.name,
            tool=tool.name,
            arguments=arguments,
        )

        try:
            result = await self._client.execute_tool(
                server,
                tool.name,
                arguments,
                timeout=timeout,
                extra_volumes=extra_volumes,
            )
            return HubExecutionResult(
                success=True,
                server_name=server.name,
                tool_name=tool.name,
                result=result,
            )

        except HubClientError as e:
            return HubExecutionResult(
                success=False,
                server_name=server.name,
                tool_name=tool.name,
                error=str(e),
            )

    def list_servers(self) -> list[dict[str, Any]]:
        """List all registered servers with their status.

        :returns: List of server info dicts.

        """
        servers = []
        for server in self._registry.servers:
            session = self._client.get_persistent_session(server.name)
            servers.append({
                "name": server.name,
                "identifier": server.identifier,
                "type": server.config.type.value,
                "enabled": server.config.enabled,
                "category": server.config.category,
                "description": server.config.description,
                "persistent": server.config.persistent,
                "persistent_session_active": session is not None and session.alive,
                "discovered": server.discovered,
                "tool_count": len(server.tools),
                "error": server.discovery_error,
            })
        return servers

    def list_tools(self) -> list[dict[str, Any]]:
        """List all discovered tools.

        :returns: List of tool info dicts.

        """
        tools = []
        for tool in self._registry.get_all_tools():
            tools.append({
                "identifier": tool.identifier,
                "name": tool.name,
                "server": tool.server_name,
                "description": tool.description,
                "parameters": [p.model_dump() for p in tool.parameters],
            })
        return tools

    def get_tool_schema(self, identifier: str) -> dict[str, Any] | None:
        """Get the JSON Schema for a tool's input.

        :param identifier: Tool identifier.
        :returns: JSON Schema dict or None if not found.

        """
        _, tool = self._registry.find_tool(identifier)
        if tool:
            return tool.input_schema
        return None

    # ------------------------------------------------------------------
    # Persistent session management
    # ------------------------------------------------------------------

    async def start_persistent_server(self, server_name: str, extra_volumes: list[str] | None = None) -> dict[str, Any]:
        """Start a persistent container session for a server.

        The container stays running between tool calls, allowing stateful
        interactions (e.g., radare2 sessions, long-running fuzzing).

        :param server_name: Name of the hub server to start.
        :param extra_volumes: Additional host:container volume mounts to inject.
        :returns: Session status dictionary.
        :raises ValueError: If server not found.

        """
        logger = get_logger()
        server = self._registry.get_server(server_name)
        if not server:
            msg = f"Server '{server_name}' not found"
            raise ValueError(msg)

        session = await self._client.start_persistent_session(server.config, extra_volumes=extra_volumes)

        # Auto-discover tools on the new session
        try:
            tools = await self._client.discover_tools(server)
            self._registry.update_server_tools(server_name, tools)
        except HubClientError as e:
            logger.warning(
                "Tool discovery failed on persistent session",
                server=server_name,
                error=str(e),
            )

        # Include discovered tools in the result so agent knows what's available
        discovered_tools = []
        server_obj = self._registry.get_server(server_name)
        if server_obj:
            for tool in server_obj.tools:
                discovered_tools.append({
                    "identifier": tool.identifier,
                    "name": tool.name,
                    "description": tool.description,
                })

        return {
            "server_name": session.server_name,
            "container_name": session.container_name,
            "alive": session.alive,
            "initialized": session.initialized,
            "started_at": session.started_at.isoformat(),
            "tools": discovered_tools,
            "tool_count": len(discovered_tools),
        }

    async def stop_persistent_server(self, server_name: str) -> bool:
        """Stop a persistent container session.

        :param server_name: Server name.
        :returns: True if a session was stopped.

        """
        return await self._client.stop_persistent_session(server_name)

    def get_persistent_status(self, server_name: str) -> dict[str, Any] | None:
        """Get status of a persistent session.

        :param server_name: Server name.
        :returns: Status dict or None if no session.

        """
        session = self._client.get_persistent_session(server_name)
        if not session:
            return None

        from datetime import datetime, timezone  # noqa: PLC0415

        return {
            "server_name": session.server_name,
            "container_name": session.container_name,
            "alive": session.alive,
            "initialized": session.initialized,
            "started_at": session.started_at.isoformat(),
            "uptime_seconds": int(
                (datetime.now(tz=timezone.utc) - session.started_at).total_seconds()
            ),
        }

    def list_persistent_sessions(self) -> list[dict[str, Any]]:
        """List all persistent sessions.

        :returns: List of session status dicts.

        """
        return self._client.list_persistent_sessions()

    async def stop_all_persistent_servers(self) -> int:
        """Stop all persistent sessions.

        :returns: Number of sessions stopped.

        """
        return await self._client.stop_all_persistent_sessions()

    # ------------------------------------------------------------------
    # Continuous session management
    # ------------------------------------------------------------------

    async def start_continuous_tool(
        self,
        server_name: str,
        start_tool: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Start a continuous hub tool session.

        Ensures a persistent container is running, then calls the start tool
        (e.g., ``cargo_fuzz_start``) which returns a session_id. Tracks the
        session for subsequent status/stop calls.

        :param server_name: Hub server name.
        :param start_tool: Name of the start tool on the server.
        :param arguments: Arguments for the start tool.
        :returns: Start result including session_id.
        :raises ValueError: If server not found.

        """
        logger = get_logger()

        server = self._registry.get_server(server_name)
        if not server:
            msg = f"Server '{server_name}' not found"
            raise ValueError(msg)

        # Ensure persistent session is running
        persistent = self._client.get_persistent_session(server_name)
        if not persistent or not persistent.alive:
            logger.info(
                "Auto-starting persistent session for continuous tool",
                server=server_name,
            )
            await self._client.start_persistent_session(server.config)
            # Discover tools on the new session
            try:
                tools = await self._client.discover_tools(server)
                self._registry.update_server_tools(server_name, tools)
            except HubClientError as e:
                logger.warning(
                    "Tool discovery failed on persistent session",
                    server=server_name,
                    error=str(e),
                )

        # Call the start tool
        result = await self._client.execute_tool(
            server, start_tool, arguments,
        )

        # Extract session_id from result
        content_text = ""
        for item in result.get("content", []):
            if item.get("type") == "text":
                content_text = item.get("text", "")
                break

        import json  # noqa: PLC0415

        try:
            start_result = json.loads(content_text) if content_text else result
        except json.JSONDecodeError:
            start_result = result

        session_id = start_result.get("session_id", "")

        if session_id:
            from datetime import datetime, timezone  # noqa: PLC0415

            self._continuous_sessions[session_id] = {
                "session_id": session_id,
                "server_name": server_name,
                "start_tool": start_tool,
                "status_tool": start_tool.replace("_start", "_status"),
                "stop_tool": start_tool.replace("_start", "_stop"),
                "started_at": datetime.now(tz=timezone.utc).isoformat(),
                "status": "running",
            }

        return start_result

    async def get_continuous_tool_status(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Get status of a continuous hub tool session.

        :param session_id: Session ID from start_continuous_tool.
        :returns: Status dict from the hub server's status tool.
        :raises ValueError: If session not found.

        """
        session_info = self._continuous_sessions.get(session_id)
        if not session_info:
            msg = f"Unknown continuous session: {session_id}"
            raise ValueError(msg)

        server = self._registry.get_server(session_info["server_name"])
        if not server:
            msg = f"Server '{session_info['server_name']}' not found"
            raise ValueError(msg)

        result = await self._client.execute_tool(
            server,
            session_info["status_tool"],
            {"session_id": session_id},
        )

        # Parse the text content
        content_text = ""
        for item in result.get("content", []):
            if item.get("type") == "text":
                content_text = item.get("text", "")
                break

        import json  # noqa: PLC0415

        try:
            return json.loads(content_text) if content_text else result
        except json.JSONDecodeError:
            return result

    async def stop_continuous_tool(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Stop a continuous hub tool session.

        :param session_id: Session ID to stop.
        :returns: Final results from the hub server's stop tool.
        :raises ValueError: If session not found.

        """
        session_info = self._continuous_sessions.get(session_id)
        if not session_info:
            msg = f"Unknown continuous session: {session_id}"
            raise ValueError(msg)

        server = self._registry.get_server(session_info["server_name"])
        if not server:
            msg = f"Server '{session_info['server_name']}' not found"
            raise ValueError(msg)

        result = await self._client.execute_tool(
            server,
            session_info["stop_tool"],
            {"session_id": session_id},
        )

        # Parse the text content
        content_text = ""
        for item in result.get("content", []):
            if item.get("type") == "text":
                content_text = item.get("text", "")
                break

        import json  # noqa: PLC0415

        try:
            stop_result = json.loads(content_text) if content_text else result
        except json.JSONDecodeError:
            stop_result = result

        # Update session tracking
        session_info["status"] = "stopped"

        return stop_result

    def list_continuous_sessions(self) -> list[dict[str, Any]]:
        """List all tracked continuous sessions.

        :returns: List of continuous session info dicts.

        """
        return list(self._continuous_sessions.values())
