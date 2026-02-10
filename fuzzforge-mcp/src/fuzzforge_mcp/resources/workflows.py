"""Workflow resources for FuzzForge MCP.

Note: In FuzzForge OSS, workflows are defined at runtime rather than
stored. This resource provides documentation about workflow capabilities.

"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP


mcp: FastMCP = FastMCP()


@mcp.resource("fuzzforge://workflows/help")
async def get_workflow_help() -> dict[str, Any]:
    """Get help information about creating workflows.

    Workflows in FuzzForge OSS are defined at execution time rather
    than stored. Use the execute_workflow tool with step definitions.

    :return: Workflow documentation.

    """
    return {
        "description": "Workflows chain multiple modules together",
        "usage": "Use the execute_workflow tool with step definitions",
        "example": {
            "workflow_name": "security-audit",
            "steps": [
                {
                    "module": "compile-contracts",
                    "configuration": {"solc_version": "0.8.0"},
                },
                {
                    "module": "slither",
                    "configuration": {},
                },
                {
                    "module": "echidna",
                    "configuration": {"test_limit": 10000},
                },
            ],
        },
        "step_format": {
            "module": "Module identifier (required)",
            "configuration": "Module-specific configuration (optional)",
            "name": "Step name for logging (optional)",
        },
    }
