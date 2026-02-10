"""FuzzForge MCP Resources."""

from fastmcp import FastMCP

from fuzzforge_mcp.resources import executions, modules, project, workflows

mcp: FastMCP = FastMCP()

mcp.mount(executions.mcp)
mcp.mount(modules.mcp)
mcp.mount(project.mcp)
mcp.mount(workflows.mcp)

__all__ = [
    "mcp",
]
