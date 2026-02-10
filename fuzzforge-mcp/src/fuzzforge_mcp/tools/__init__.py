"""FuzzForge MCP Tools."""

from fastmcp import FastMCP

from fuzzforge_mcp.tools import modules, projects, workflows

mcp: FastMCP = FastMCP()

mcp.mount(modules.mcp)
mcp.mount(projects.mcp)
mcp.mount(workflows.mcp)

__all__ = [
    "mcp",
]

