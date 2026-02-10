"""FuzzForge CLI context management."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from fuzzforge_runner import Runner, Settings

if TYPE_CHECKING:
    from typer import Context as TyperContext


class Context:
    """CLI context holding the runner instance and settings."""

    _runner: Runner
    _project_path: Path

    def __init__(self, runner: Runner, project_path: Path) -> None:
        """Initialize an instance of the class.

        :param runner: FuzzForge runner instance.
        :param project_path: Path to the current project.

        """
        self._runner = runner
        self._project_path = project_path

    def get_runner(self) -> Runner:
        """Get the runner instance.

        :return: Runner instance.

        """
        return self._runner

    def get_project_path(self) -> Path:
        """Get the current project path.

        :return: Project path.

        """
        return self._project_path


def get_runner(context: TyperContext) -> Runner:
    """Get runner from Typer context.

    :param context: Typer context.
    :return: Runner instance.

    """
    return cast("Context", context.obj).get_runner()


def get_project_path(context: TyperContext) -> Path:
    """Get project path from Typer context.

    :param context: Typer context.
    :return: Project path.

    """
    return cast("Context", context.obj).get_project_path()
