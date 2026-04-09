"""SecPipe MCP Server Application.

This is the main entry point for the SecPipe MCP server, providing
AI agents with tools to discover and execute MCP hub tools for
security research.

"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

from secpipe_mcp import resources, tools
from secpipe_mcp.settings import Settings

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
    name="SecPipe MCP Server",
    instructions="""
SecPipe is a security research orchestration platform. Use these tools to:

1. **List hub servers**: Discover registered MCP tool servers
2. **Discover tools**: Find available tools from hub servers
3. **Execute hub tools**: Run security tools in isolated containers
4. **Manage projects**: Initialize and configure projects
5. **Get results**: Retrieve execution results

Typical workflow:
1. Initialize a project with `init_project`
2. Set project assets with `set_project_assets` — path to the directory containing
   target files (firmware images, binaries, source code, etc.)
3. List available hub servers with `list_hub_servers`
4. Discover tools from servers with `discover_hub_tools`
5. Execute hub tools with `execute_hub_tool`

Skill packs:
Use `list_skills` to see available analysis pipelines (e.g. firmware-analysis).
Load one with `load_skill("firmware-analysis")` to get domain-specific guidance
and a scoped list of relevant hub servers. Skill packs describe the methodology —
follow the pipeline steps while adapting to what you find at each stage.

Agent context convention:
When you call `discover_hub_tools`, some servers return an `agent_context` field
with usage tips, known issues, rule templates, and workflow guidance. Always read
this context before using the server's tools.

Artifact tracking:
After each `execute_hub_tool` call, new output files are automatically tracked.
Use `list_artifacts` to find files produced by previous tools instead of parsing
paths from tool output text. Filter by source server or file type.

File access in containers:
- Assets set via `set_project_assets` are mounted read-only at `/app/uploads/` and `/app/samples/`
- A writable output directory is mounted at `/app/output/` — use it for extraction results, reports, etc.
- Always use container paths (e.g. `/app/uploads/file`) when passing file arguments to hub tools

Stateful tools:
- Some tools require multi-step sessions. Use `start_hub_server` to launch
  a persistent container, then `execute_hub_tool` calls reuse that container. Stop with `stop_hub_server`.
""",
    lifespan=lifespan,
)

mcp.add_middleware(middleware=ErrorHandlingMiddleware())

mcp.mount(resources.mcp)
mcp.mount(tools.mcp)

# HTTP app for testing (primary mode is stdio)
app = mcp.http_app()

