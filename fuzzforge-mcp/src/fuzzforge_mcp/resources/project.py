"""Project resources for FuzzForge MCP."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from fuzzforge_mcp.dependencies import get_project_path, get_runner

if TYPE_CHECKING:
    from fuzzforge_runner import Runner


mcp: FastMCP = FastMCP()


@mcp.resource("fuzzforge://project")
async def get_project() -> dict[str, Any]:
    """Get information about the current project.

    Returns the current project configuration including paths
    and available executions.

    :return: Project information dictionary.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        executions = runner.list_executions(project_path)
        assets_path = runner.storage.get_project_assets_path(project_path)

        return {
            "path": str(project_path),
            "name": project_path.name,
            "has_assets": assets_path is not None,
            "assets_path": str(assets_path) if assets_path else None,
            "execution_count": len(executions),
            "recent_executions": executions[:10],  # Last 10 executions
        }

    except Exception as exception:
        message: str = f"Failed to get project info: {exception}"
        raise ResourceError(message) from exception


@mcp.resource("fuzzforge://project/settings")
async def get_project_settings() -> dict[str, Any]:
    """Get current FuzzForge settings.

    Returns the active configuration for the MCP server including
    engine, storage, and project settings.

    :return: Settings dictionary.

    """
    from fuzzforge_mcp.dependencies import get_settings

    try:
        settings = get_settings()

        return {
            "engine": {
                "type": settings.engine.type,
                "socket": settings.engine.socket,
            },
            "storage": {
                "path": str(settings.storage.path),
            },
            "project": {
                "path": str(settings.project.path),
                "modules_path": str(settings.modules_path),
            },
            "debug": settings.debug,
        }

    except Exception as exception:
        message: str = f"Failed to get settings: {exception}"
        raise ResourceError(message) from exception

