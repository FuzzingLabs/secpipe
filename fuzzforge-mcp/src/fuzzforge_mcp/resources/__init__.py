"""FuzzForge MCP Resources."""

from fastmcp import FastMCP

from fuzzforge_mcp.resources import executions, project

mcp: FastMCP = FastMCP()

mcp.mount(executions.mcp)
mcp.mount(project.mcp)

__all__ = [
    "mcp",
]
