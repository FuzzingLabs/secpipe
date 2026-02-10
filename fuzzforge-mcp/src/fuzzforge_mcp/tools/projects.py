"""Project management tools for FuzzForge MCP."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from fuzzforge_mcp.dependencies import get_project_path, get_runner, set_current_project_path

if TYPE_CHECKING:
    from fuzzforge_runner import Runner


mcp: FastMCP = FastMCP()


@mcp.tool
async def init_project(project_path: str | None = None) -> dict[str, Any]:
    """Initialize a new FuzzForge project.

    Creates a `.fuzzforge/` directory inside the project for storing:
    - assets/: Input files (source code, etc.)
    - inputs/: Prepared module inputs (for debugging)
    - runs/: Execution results from each module

    This should be called before executing modules or workflows.

    :param project_path: Path to the project directory. If not provided, uses current directory.
    :return: Project initialization result.

    """
    runner: Runner = get_runner()

    try:
        path = Path(project_path) if project_path else get_project_path()
        
        # Track this as the current active project
        set_current_project_path(path)
        
        storage_path = runner.init_project(path)

        return {
            "success": True,
            "project_path": str(path),
            "storage_path": str(storage_path),
            "message": f"Project initialized. Storage at {path}/.fuzzforge/",
        }

    except Exception as exception:
        message: str = f"Failed to initialize project: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def set_project_assets(assets_path: str) -> dict[str, Any]:
    """Set the initial assets for a project.

    Assets are input files that will be provided to modules during execution.
    This could be source code, contracts, binaries, etc.

    :param assets_path: Path to assets file (archive) or directory.
    :return: Result including stored assets path.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        stored_path = runner.set_project_assets(
            project_path=project_path,
            assets_path=Path(assets_path),
        )

        return {
            "success": True,
            "project_path": str(project_path),
            "assets_path": str(stored_path),
            "message": f"Assets stored from {assets_path}",
        }

    except Exception as exception:
        message: str = f"Failed to set project assets: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def list_executions() -> dict[str, Any]:
    """List all executions for the current project.

    Returns a list of execution IDs that can be used to retrieve results.

    :return: List of execution IDs.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        executions = runner.list_executions(project_path)

        return {
            "success": True,
            "project_path": str(project_path),
            "executions": executions,
            "count": len(executions),
        }

    except Exception as exception:
        message: str = f"Failed to list executions: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def get_execution_results(execution_id: str, extract_to: str | None = None) -> dict[str, Any]:
    """Get results for a specific execution.

    :param execution_id: The execution ID to retrieve results for.
    :param extract_to: Optional directory to extract results to.
    :return: Result including path to results archive.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        results_path = runner.get_execution_results(project_path, execution_id)

        if results_path is None:
            return {
                "success": False,
                "execution_id": execution_id,
                "error": "Execution results not found",
            }

        result = {
            "success": True,
            "execution_id": execution_id,
            "results_path": str(results_path),
        }

        # Extract if requested
        if extract_to:
            extracted_path = runner.extract_results(results_path, Path(extract_to))
            result["extracted_path"] = str(extracted_path)

        return result

    except Exception as exception:
        message: str = f"Failed to get execution results: {exception}"
        raise ToolError(message) from exception
