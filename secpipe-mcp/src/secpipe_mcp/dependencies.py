"""Dependency injection helpers for SecPipe MCP."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fastmcp.server.dependencies import get_context

from secpipe_mcp.exceptions import SecPipeMCPError
from secpipe_mcp.settings import Settings
from secpipe_mcp.storage import LocalStorage

if TYPE_CHECKING:
    from fastmcp import Context


# Track the current active project path (set by init_project)
_current_project_path: Path | None = None

# Singleton storage instance
_storage: LocalStorage | None = None

# Currently loaded skill pack (set by load_skill)
_active_skill: dict[str, Any] | None = None


def set_current_project_path(project_path: Path) -> None:
    """Set the current project path.

    Called by init_project to track which project is active.

    :param project_path: Path to the project directory.

    """
    global _current_project_path
    _current_project_path = project_path


def get_settings() -> Settings:
    """Get MCP server settings from context.

    :return: Settings instance.
    :raises SecPipeMCPError: If settings not available.

    """
    context: Context = get_context()
    if context.request_context is None:
        message: str = "Request context not available"
        raise SecPipeMCPError(message)
    return cast("Settings", context.request_context.lifespan_context)


def get_project_path() -> Path:
    """Get the current project path.

    Returns the project path set by init_project, or falls back to
    the current working directory if no project has been initialized.

    :return: Path to the current project.

    """
    global _current_project_path
    if _current_project_path is not None:
        return _current_project_path
    # Fall back to current working directory (where the AI agent is working)
    return Path.cwd()


def get_storage() -> LocalStorage:
    """Get the storage backend instance.

    :return: LocalStorage instance.

    """
    global _storage
    if _storage is None:
        settings = get_settings()
        _storage = LocalStorage(settings.storage.path)
    return _storage


def set_active_skill(skill: dict[str, Any] | None) -> None:
    """Set (or clear) the currently loaded skill pack.

    :param skill: Parsed skill dict, or None to unload.

    """
    global _active_skill
    _active_skill = skill


def get_active_skill() -> dict[str, Any] | None:
    """Get the currently loaded skill pack.

    :return: Active skill dict, or None if no skill is loaded.

    """
    return _active_skill
