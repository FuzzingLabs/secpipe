"""MCP tool tests for SecPipe AI.

Tests the MCP tools that are available in SecPipe AI.
"""

import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import Client
    from fastmcp.client import FastMCPTransport


async def test_init_project_tool_exists(
    mcp_client: "Client[FastMCPTransport]",
) -> None:
    """Test that the init_project tool is available."""
    tools = await mcp_client.list_tools()
    tool_names = [tool.name for tool in tools]
    
    assert "init_project" in tool_names


async def test_mcp_has_expected_tool_count(
    mcp_client: "Client[FastMCPTransport]",
) -> None:
    """Test that MCP has the expected number of tools."""
    tools = await mcp_client.list_tools()
    
    # Should have project tools + hub tools
    assert len(tools) >= 2
