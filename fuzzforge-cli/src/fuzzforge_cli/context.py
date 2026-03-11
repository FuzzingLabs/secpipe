"""FuzzForge CLI context management."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from fuzzforge_mcp.storage import LocalStorage  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from typer import Context as TyperContext


class Context:
    """CLI context holding the storage instance and settings."""

    _storage: LocalStorage
    _project_path: Path

    def __init__(self, storage: LocalStorage, project_path: Path) -> None:
        """Initialize an instance of the class.

        :param storage: FuzzForge local storage instance.
        :param project_path: Path to the current project.

        """
        self._storage = storage
        self._project_path = project_path

    def get_storage(self) -> LocalStorage:
        """Get the storage instance.

        :return: LocalStorage instance.

        """
        return self._storage

    def get_project_path(self) -> Path:
        """Get the current project path.

        :return: Project path.

        """
        return self._project_path


def get_storage(context: TyperContext) -> LocalStorage:
    """Get storage from Typer context.

    :param context: Typer context.
    :return: LocalStorage instance.

    """
    return cast("Context", context.obj).get_storage()


def get_project_path(context: TyperContext) -> Path:
    """Get project path from Typer context.

    :param context: Typer context.
    :return: Project path.

    """
    return cast("Context", context.obj).get_project_path()
