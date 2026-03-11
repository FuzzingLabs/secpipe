"""MCP Hub tools for FuzzForge MCP server.

This module provides tools for interacting with external MCP servers
through the FuzzForge hub. AI agents can:
- List available hub servers and their tools
- Discover tools from hub servers
- Execute hub tools

"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fuzzforge_common.hub import HubExecutor, HubServerConfig, HubServerType

from fuzzforge_mcp.dependencies import get_settings

mcp: FastMCP = FastMCP()

# Global hub executor instance (lazy initialization)
_hub_executor: HubExecutor | None = None


def _get_hub_executor() -> HubExecutor:
    """Get or create the hub executor instance.

    :returns: Hub executor instance.
    :raises ToolError: If hub is disabled.

    """
    global _hub_executor

    settings = get_settings()

    if not settings.hub.enabled:
        msg = "MCP Hub is disabled. Enable it via FUZZFORGE_HUB__ENABLED=true"
        raise ToolError(msg)

    if _hub_executor is None:
        config_path = settings.hub.config_path
        _hub_executor = HubExecutor(
            config_path=config_path,
            timeout=settings.hub.timeout,
        )

    return _hub_executor


@mcp.tool
async def list_hub_servers() -> dict[str, Any]:
    """List all registered MCP hub servers.

    Returns information about configured hub servers, including
    their connection type, status, and discovered tool count.

    :return: Dictionary with list of hub servers.

    """
    try:
        executor = _get_hub_executor()
        servers = executor.list_servers()

        return {
            "servers": servers,
            "count": len(servers),
            "enabled_count": len([s for s in servers if s["enabled"]]),
        }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to list hub servers: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def discover_hub_tools(server_name: str | None = None) -> dict[str, Any]:
    """Discover tools from hub servers.

    Connects to hub servers and retrieves their available tools.
    If server_name is provided, only discovers from that server.
    Otherwise discovers from all enabled servers.

    :param server_name: Optional specific server to discover from.
    :return: Dictionary with discovered tools.

    """
    try:
        executor = _get_hub_executor()

        if server_name:
            tools = await executor.discover_server_tools(server_name)
            return {
                "server": server_name,
                "tools": [
                    {
                        "identifier": t.identifier,
                        "name": t.name,
                        "description": t.description,
                        "parameters": [p.model_dump() for p in t.parameters],
                    }
                    for t in tools
                ],
                "count": len(tools),
            }
        else:
            results = await executor.discover_all_tools()
            all_tools = []
            for server, tools in results.items():
                for tool in tools:
                    all_tools.append({
                        "identifier": tool.identifier,
                        "name": tool.name,
                        "server": server,
                        "description": tool.description,
                        "parameters": [p.model_dump() for p in tool.parameters],
                    })

            return {
                "servers_discovered": len(results),
                "tools": all_tools,
                "count": len(all_tools),
            }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to discover hub tools: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def list_hub_tools() -> dict[str, Any]:
    """List all discovered hub tools.

    Returns tools that have been previously discovered from hub servers.
    Run discover_hub_tools first if no tools are listed.

    :return: Dictionary with list of discovered tools.

    """
    try:
        executor = _get_hub_executor()
        tools = executor.list_tools()

        return {
            "tools": tools,
            "count": len(tools),
        }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to list hub tools: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def execute_hub_tool(
    identifier: str,
    arguments: dict[str, Any] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Execute a tool from a hub server.

    :param identifier: Tool identifier (format: hub:server:tool or server:tool).
    :param arguments: Tool arguments matching the tool's input schema.
    :param timeout: Optional execution timeout in seconds.
    :return: Tool execution result.

    Example identifiers:
    - "hub:nmap:nmap_scan"
    - "nmap:nmap_scan"
    - "hub:nuclei:nuclei_scan"

    """
    try:
        executor = _get_hub_executor()

        result = await executor.execute_tool(
            identifier=identifier,
            arguments=arguments or {},
            timeout=timeout,
        )

        return result.to_dict()

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Hub tool execution failed: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def get_hub_tool_schema(identifier: str) -> dict[str, Any]:
    """Get the input schema for a hub tool.

    Returns the JSON Schema that describes the tool's expected arguments.

    :param identifier: Tool identifier (format: hub:server:tool or server:tool).
    :return: JSON Schema for the tool's input.

    """
    try:
        executor = _get_hub_executor()
        schema = executor.get_tool_schema(identifier)

        if schema is None:
            msg = f"Tool '{identifier}' not found. Run discover_hub_tools first."
            raise ToolError(msg)

        return {
            "identifier": identifier,
            "schema": schema,
        }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to get tool schema: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def add_hub_server(
    name: str,
    server_type: str,
    image: str | None = None,
    command: list[str] | None = None,
    url: str | None = None,
    category: str | None = None,
    description: str | None = None,
    capabilities: list[str] | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Add a new MCP server to the hub.

    Register a new external MCP server that can be used for tool discovery
    and execution. Servers can be Docker images, local commands, or SSE endpoints.

    :param name: Unique name for the server (e.g., "nmap", "nuclei").
    :param server_type: Connection type ("docker", "command", or "sse").
    :param image: Docker image name (for docker type).
    :param command: Command and args (for command type).
    :param url: SSE endpoint URL (for sse type).
    :param category: Category for grouping (e.g., "reconnaissance").
    :param description: Human-readable description.
    :param capabilities: Docker capabilities to add (e.g., ["NET_RAW"]).
    :param environment: Environment variables to pass.
    :return: Information about the added server.

    Examples:
    - Docker: add_hub_server("nmap", "docker", image="nmap-mcp:latest", capabilities=["NET_RAW"])
    - Command: add_hub_server("custom", "command", command=["python", "server.py"])

    """
    try:
        executor = _get_hub_executor()

        # Parse server type
        try:
            stype = HubServerType(server_type)
        except ValueError:
            msg = f"Invalid server type: {server_type}. Use 'docker', 'command', or 'sse'."
            raise ToolError(msg) from None

        # Validate required fields based on type
        if stype == HubServerType.DOCKER and not image:
            msg = "Docker image required for docker type"
            raise ToolError(msg)
        if stype == HubServerType.COMMAND and not command:
            msg = "Command required for command type"
            raise ToolError(msg)
        if stype == HubServerType.SSE and not url:
            msg = "URL required for sse type"
            raise ToolError(msg)

        config = HubServerConfig(
            name=name,
            type=stype,
            image=image,
            command=command,
            url=url,
            category=category,
            description=description,
            capabilities=capabilities or [],
            environment=environment or {},
        )

        server = executor.add_server(config)

        return {
            "success": True,
            "server": {
                "name": server.name,
                "identifier": server.identifier,
                "type": server.config.type.value,
                "enabled": server.config.enabled,
            },
            "message": f"Server '{name}' added. Use discover_hub_tools('{name}') to discover its tools.",
        }

    except ValueError as e:
        msg = f"Failed to add server: {e}"
        raise ToolError(msg) from e
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to add hub server: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def start_hub_server(server_name: str) -> dict[str, Any]:
    """Start a persistent container session for a hub server.

    Starts a Docker container that stays running between tool calls,
    allowing stateful interactions. Tools are auto-discovered on start.

    Use this for servers like radare2 or ghidra where you want to
    keep an analysis session open across multiple tool calls.

    After starting, use execute_hub_tool as normal - calls will be
    routed to the persistent container automatically.

    :param server_name: Name of the hub server to start (e.g., "radare2-mcp").
    :return: Session status with container name and start time.

    """
    try:
        executor = _get_hub_executor()

        result = await executor.start_persistent_server(server_name)

        return {
            "success": True,
            "session": result,
            "tools": result.get("tools", []),
            "tool_count": result.get("tool_count", 0),
            "message": (
                f"Persistent session started for '{server_name}'. "
                f"Discovered {result.get('tool_count', 0)} tools. "
                "Use execute_hub_tool to call them — they will reuse this container. "
                f"Stop with stop_hub_server('{server_name}') when done."
            ),
        }

    except ValueError as e:
        msg = f"Server not found: {e}"
        raise ToolError(msg) from e
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to start persistent server: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def stop_hub_server(server_name: str) -> dict[str, Any]:
    """Stop a persistent container session for a hub server.

    Terminates the running Docker container and cleans up resources.
    After stopping, tool calls will fall back to ephemeral mode
    (a new container per call).

    :param server_name: Name of the hub server to stop.
    :return: Result indicating if the session was stopped.

    """
    try:
        executor = _get_hub_executor()

        stopped = await executor.stop_persistent_server(server_name)

        if stopped:
            return {
                "success": True,
                "message": f"Persistent session for '{server_name}' stopped and container removed.",
            }
        else:
            return {
                "success": False,
                "message": f"No active persistent session found for '{server_name}'.",
            }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to stop persistent server: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def hub_server_status(server_name: str | None = None) -> dict[str, Any]:
    """Get status of persistent hub server sessions.

    If server_name is provided, returns status for that specific server.
    Otherwise returns status for all active persistent sessions.

    :param server_name: Optional specific server to check.
    :return: Session status information.

    """
    try:
        executor = _get_hub_executor()

        if server_name:
            status = executor.get_persistent_status(server_name)
            if status:
                return {"active": True, "session": status}
            else:
                return {
                    "active": False,
                    "message": f"No active persistent session for '{server_name}'.",
                }
        else:
            sessions = executor.list_persistent_sessions()
            return {
                "active_sessions": sessions,
                "count": len(sessions),
            }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to get server status: {e}"
        raise ToolError(msg) from e


# ------------------------------------------------------------------
# Continuous mode tools
# ------------------------------------------------------------------


@mcp.tool
async def start_continuous_hub_tool(
    server_name: str,
    start_tool: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start a continuous/background tool on a hub server.

    Automatically starts a persistent container if not already running,
    then calls the server's start tool (e.g., cargo_fuzz_start) which
    launches a background process and returns a session_id.

    The tool runs indefinitely until stopped with stop_continuous_hub_tool.
    Use get_continuous_hub_status to monitor progress.

    Example workflow for continuous cargo fuzzing:
    1. start_continuous_hub_tool("cargo-fuzzer-mcp", "cargo_fuzz_start", {"project_path": "/data/myproject"})
    2. get_continuous_hub_status(session_id)  -- poll every 10-30s
    3. stop_continuous_hub_tool(session_id)   -- when done

    :param server_name: Hub server name (e.g., "cargo-fuzzer-mcp").
    :param start_tool: Name of the start tool on the server.
    :param arguments: Arguments for the start tool.
    :return: Start result including session_id for monitoring.

    """
    try:
        executor = _get_hub_executor()

        result = await executor.start_continuous_tool(
            server_name=server_name,
            start_tool=start_tool,
            arguments=arguments or {},
        )

        # Return the server's response directly — it already contains
        # session_id, status, targets, and a message.
        return result

    except ValueError as e:
        msg = f"Server not found: {e}"
        raise ToolError(msg) from e
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to start continuous tool: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def get_continuous_hub_status(session_id: str) -> dict[str, Any]:
    """Get live status of a continuous hub tool session.

    Returns current metrics, progress, and recent output from the
    running tool. Call periodically (every 10-30 seconds) to monitor.

    :param session_id: Session ID returned by start_continuous_hub_tool.
    :return: Current status with metrics (executions, coverage, crashes, etc.).

    """
    try:
        executor = _get_hub_executor()

        return await executor.get_continuous_tool_status(session_id)

    except ValueError as e:
        msg = str(e)
        raise ToolError(msg) from e
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to get continuous status: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def stop_continuous_hub_tool(session_id: str) -> dict[str, Any]:
    """Stop a running continuous hub tool session.

    Gracefully stops the background process and returns final results
    including total metrics and any artifacts (crash files, etc.).

    :param session_id: Session ID of the session to stop.
    :return: Final metrics and results summary.

    """
    try:
        executor = _get_hub_executor()

        return await executor.stop_continuous_tool(session_id)

    except ValueError as e:
        msg = str(e)
        raise ToolError(msg) from e
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to stop continuous tool: {e}"
        raise ToolError(msg) from e


@mcp.tool
async def list_continuous_hub_sessions() -> dict[str, Any]:
    """List all active and recent continuous hub tool sessions.

    :return: List of sessions with their status and server info.

    """
    try:
        executor = _get_hub_executor()

        sessions = executor.list_continuous_sessions()
        return {
            "sessions": sessions,
            "count": len(sessions),
        }

    except Exception as e:
        if isinstance(e, ToolError):
            raise
        msg = f"Failed to list continuous sessions: {e}"
        raise ToolError(msg) from e
