"""Project management tools for FuzzForge MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from fuzzforge_mcp.dependencies import get_project_path, get_storage, set_current_project_path


mcp: FastMCP = FastMCP()


@mcp.tool
async def init_project(project_path: str | None = None) -> dict[str, Any]:
    """Initialize a new FuzzForge project.

    Creates a `.fuzzforge/` directory inside the project for storing:
    - config.json: Project configuration
    - runs/: Execution results

    This should be called before executing hub tools.

    :param project_path: Path to the project directory. If not provided, uses current directory.
    :return: Project initialization result.

    """
    storage = get_storage()

    try:
        path = Path(project_path) if project_path else get_project_path()

        # Track this as the current active project
        set_current_project_path(path)

        storage_path = storage.init_project(path)

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
    """Set the initial assets (source code) for a project.

    This sets the DEFAULT source directory that will be mounted into
    hub tool containers via volume mounts.

    :param assets_path: Path to the project source directory.
    :return: Result including stored assets path.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        stored_path = storage.set_project_assets(
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
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        executions = storage.list_executions(project_path)

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
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        results_path = storage.get_execution_results(project_path, execution_id)

        if results_path is None:
            return {
                "success": False,
                "execution_id": execution_id,
                "error": "Execution results not found",
            }

        result: dict[str, Any] = {
            "success": True,
            "execution_id": execution_id,
            "results_path": str(results_path),
        }

        # Extract if requested
        if extract_to:
            extracted_path = storage.extract_results(results_path, Path(extract_to))
            result["extracted_path"] = str(extracted_path)

        return result

    except Exception as exception:
        message: str = f"Failed to get execution results: {exception}"
        raise ToolError(message) from exception
