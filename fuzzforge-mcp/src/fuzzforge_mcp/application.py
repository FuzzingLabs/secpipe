"""FuzzForge MCP Server Application.

This is the main entry point for the FuzzForge MCP server, providing
AI agents with tools to execute security research modules.

"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

from fuzzforge_mcp import resources, tools
from fuzzforge_runner import Settings

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

1. **List modules**: Discover available security research modules
2. **Execute modules**: Run modules in isolated containers
3. **Execute workflows**: Chain multiple modules together
4. **Manage projects**: Initialize and configure projects
5. **Get results**: Retrieve execution results

Typical workflow:
1. Initialize a project with `init_project`
2. Set project assets with `set_project_assets` (optional)
3. List available modules with `list_modules`
4. Execute a module with `execute_module`
5. Get results with `get_execution_results`
""",
    lifespan=lifespan,
)

mcp.add_middleware(middleware=ErrorHandlingMiddleware())

mcp.mount(resources.mcp)
mcp.mount(tools.mcp)

# HTTP app for testing (primary mode is stdio)
app = mcp.http_app()

