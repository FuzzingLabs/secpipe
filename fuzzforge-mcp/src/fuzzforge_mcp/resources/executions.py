"""Execution resources for FuzzForge MCP."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from fuzzforge_mcp.dependencies import get_project_path, get_runner

if TYPE_CHECKING:
    from fuzzforge_runner import Runner


mcp: FastMCP = FastMCP()


@mcp.resource("fuzzforge://executions/")
async def list_executions() -> list[dict[str, Any]]:
    """List all executions for the current project.

    Returns a list of execution IDs and basic metadata.

    :return: List of execution information dictionaries.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        execution_ids = runner.list_executions(project_path)

        return [
            {
                "execution_id": exec_id,
                "has_results": runner.get_execution_results(project_path, exec_id) is not None,
            }
            for exec_id in execution_ids
        ]

    except Exception as exception:
        message: str = f"Failed to list executions: {exception}"
        raise ResourceError(message) from exception


@mcp.resource("fuzzforge://executions/{execution_id}")
async def get_execution(execution_id: str) -> dict[str, Any]:
    """Get information about a specific execution.

    :param execution_id: The execution ID to retrieve.
    :return: Execution information dictionary.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        results_path = runner.get_execution_results(project_path, execution_id)

        if results_path is None:
            raise ResourceError(f"Execution not found: {execution_id}")

        return {
            "execution_id": execution_id,
            "results_path": str(results_path),
            "results_exist": results_path.exists(),
        }

    except ResourceError:
        raise
    except Exception as exception:
        message: str = f"Failed to get execution: {exception}"
        raise ResourceError(message) from exception
