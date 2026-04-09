"""SecPipe MCP Server entry point."""

from secpipe_mcp.application import mcp


def main() -> None:
    """Run the SecPipe MCP server in stdio mode.

    This is the primary entry point for AI agent integration.
    The server communicates via stdin/stdout using the MCP protocol.

    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
