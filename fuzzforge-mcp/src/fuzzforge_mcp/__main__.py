"""FuzzForge MCP Server entry point."""

from fuzzforge_mcp.application import mcp


def main() -> None:
    """Run the FuzzForge MCP server in stdio mode.

    This is the primary entry point for AI agent integration.
    The server communicates via stdin/stdout using the MCP protocol.

    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
