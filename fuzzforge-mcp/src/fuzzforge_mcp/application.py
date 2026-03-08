"""FuzzForge MCP Server Application.

This is the main entry point for the FuzzForge MCP server, providing
AI agents with tools to discover and execute MCP hub tools for
security research.

"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

from fuzzforge_mcp import resources, tools
from fuzzforge_mcp.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(_: FastMCP) -> AsyncGenerator[Settings]:
    """Initialize MCP server lifespan context.

    Loads settings from environment variables and makes them
    available to all tools and resources.

    :param mcp: FastMCP server instance (unused).
    :return: Settings instance for dependency injection.

    """
    settings: Settings = Settings()
    yield settings


mcp: FastMCP = FastMCP(
    name="FuzzForge MCP Server",
    instructions="""
FuzzForge is a security research orchestration platform. Use these tools to:

1. **List hub servers**: Discover registered MCP tool servers
2. **Discover tools**: Find available tools from hub servers
3. **Execute hub tools**: Run security tools in isolated containers
4. **Manage projects**: Initialize and configure projects
5. **Get results**: Retrieve execution results

Typical workflow:
1. Initialize a project with `init_project`
2. Set project assets with `set_project_assets` (optional, only needed once for the source directory)
3. List available hub servers with `list_hub_servers`
4. Discover tools from servers with `discover_hub_tools`
5. Execute hub tools with `execute_hub_tool`

Hub workflow:
1. List available hub servers with `list_hub_servers`
2. Discover tools from servers with `discover_hub_tools`
3. Execute hub tools with `execute_hub_tool`
""",
    lifespan=lifespan,
)

mcp.add_middleware(middleware=ErrorHandlingMiddleware())

mcp.mount(resources.mcp)
mcp.mount(tools.mcp)

# HTTP app for testing (primary mode is stdio)
app = mcp.http_app()

