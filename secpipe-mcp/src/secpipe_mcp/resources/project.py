"""Project resources for SecPipe MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from secpipe_mcp.dependencies import get_project_path, get_settings, get_storage

mcp: FastMCP = FastMCP()


@mcp.resource("secpipe://project")
async def get_project() -> dict[str, Any]:
    """Get information about the current project.

    Returns the current project configuration including paths
    and available executions.

    :return: Project information dictionary.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        executions = storage.list_executions(project_path)
        assets_path = storage.get_project_assets_path(project_path)

        return {
            "path": str(project_path),
            "name": project_path.name,
            "has_assets": assets_path is not None,
            "assets_path": str(assets_path) if assets_path else None,
            "execution_count": len(executions),
            "recent_executions": executions[:10],
        }

    except Exception as exception:
        message: str = f"Failed to get project info: {exception}"
        raise ResourceError(message) from exception


@mcp.resource("secpipe://project/settings")
async def get_project_settings() -> dict[str, Any]:
    """Get current SecPipe settings.

    Returns the active configuration for the MCP server including
    engine, storage, and hub settings.

    :return: Settings dictionary.

    """
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
            "hub": {
                "enabled": settings.hub.enabled,
                "config_path": str(settings.hub.config_path),
                "timeout": settings.hub.timeout,
            },
            "debug": settings.debug,
        }

    except Exception as exception:
        message: str = f"Failed to get settings: {exception}"
        raise ResourceError(message) from exception

