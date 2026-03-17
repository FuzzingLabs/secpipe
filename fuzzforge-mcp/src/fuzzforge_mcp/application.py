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
2. Set project assets with `set_project_assets` — path to the directory containing
   target files (firmware images, binaries, source code, etc.)
3. List available hub servers with `list_hub_servers`
4. Discover tools from servers with `discover_hub_tools`
5. Execute hub tools with `execute_hub_tool`

Agent context convention:
When you call `discover_hub_tools`, some servers return an `agent_context` field
with usage tips, known issues, rule templates, and workflow guidance. Always read
this context before using the server's tools.

File access in containers:
- Assets set via `set_project_assets` are mounted read-only at `/app/uploads/` and `/app/samples/`
- A writable output directory is mounted at `/app/output/` — use it for extraction results, reports, etc.
- Always use container paths (e.g. `/app/uploads/file`) when passing file arguments to hub tools

Stateful tools:
- Some tools (e.g. radare2-mcp) require multi-step sessions. Use `start_hub_server` to launch
  a persistent container, then `execute_hub_tool` calls reuse that container. Stop with `stop_hub_server`.

Firmware analysis pipeline (when analyzing firmware images):
1. **binwalk-mcp** (`binwalk_scan` + `binwalk_extract`) — identify and extract filesystem from firmware
2. **yara-mcp** (`yara_scan_with_rules`) — scan extracted files with vulnerability rules to prioritize targets
3. **radare2-mcp** (persistent session) — confirm dangerous code paths
4. **searchsploit-mcp** (`search_exploitdb`) — query version strings from radare2 against ExploitDB
   Run steps 3 and 4 outputs feed into a final triage summary.

radare2-mcp agent context (upstream tool — no embedded context):
- Start a persistent session with `start_hub_server("radare2-mcp")` before any calls.
- IMPORTANT: the `open_file` tool requires the parameter name `file_path` (with underscore),
  not `filepath`. Example: `execute_hub_tool("hub:radare2-mcp:open_file", {"file_path": "/app/output/..."})`
- Workflow: `open_file` → `analyze` → `list_imports` → `xrefs_to` → `run_command` with `pdf @ <addr>`.
- Static binary fallback: firmware binaries are often statically linked. When `list_imports`
  returns an empty result, fall back to `list_symbols` and search for dangerous function names
  (system, strcpy, gets, popen, sprintf) in the output. Then use `xrefs_to` on their addresses.
- For string extraction, use `run_command` with `iz` (data section strings).
  The `list_all_strings` tool may return garbled output for large binaries.
- For decompilation, use `run_command` with `pdc @ <addr>` (pseudo-C) or `pdf @ <addr>`
  (annotated disassembly). The `decompile` tool may fail with "not available in current mode".
- Stop the session with `stop_hub_server("radare2-mcp")` when done.
""",
    lifespan=lifespan,
)

mcp.add_middleware(middleware=ErrorHandlingMiddleware())

mcp.mount(resources.mcp)
mcp.mount(tools.mcp)

# HTTP app for testing (primary mode is stdio)
app = mcp.http_app()

