"""FuzzForge Hub - Generic MCP server bridge.

This module provides a generic bridge to connect FuzzForge with any MCP server.
It allows AI agents to discover and execute tools from external MCP servers
(like mcp-security-hub) through the same interface as native FuzzForge modules.

The hub is server-agnostic: it doesn't hardcode any specific tools or servers.
Instead, it dynamically discovers tools by connecting to configured MCP servers
and calling their `list_tools()` method.

Supported transport types:
- docker: Run MCP server as a Docker container with stdio transport
- command: Run MCP server as a local process with stdio transport
- sse: Connect to a remote MCP server via Server-Sent Events

"""

from fuzzforge_common.hub.client import HubClient, HubClientError, PersistentSession
from fuzzforge_common.hub.executor import HubExecutionResult, HubExecutor
from fuzzforge_common.hub.models import (
    HubConfig,
    HubServer,
    HubServerConfig,
    HubServerType,
    HubTool,
    HubToolParameter,
)
from fuzzforge_common.hub.registry import HubRegistry

__all__ = [
    "HubClient",
    "HubClientError",
    "HubConfig",
    "HubExecutionResult",
    "HubExecutor",
    "HubRegistry",
    "HubServer",
    "HubServerConfig",
    "HubServerType",
    "HubTool",
    "HubToolParameter",
    "PersistentSession",
]
