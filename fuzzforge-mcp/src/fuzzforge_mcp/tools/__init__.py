"""FuzzForge MCP Tools."""

from fastmcp import FastMCP

from fuzzforge_mcp.tools import hub, projects

mcp: FastMCP = FastMCP()

mcp.mount(projects.mcp)
mcp.mount(hub.mcp)

__all__ = [
    "mcp",
]

