"""SecPipe CLI application."""

from pathlib import Path
from typing import Annotated

from secpipe_mcp.storage import LocalStorage  # type: ignore[import-untyped]
from typer import Context as TyperContext
from typer import Option, Typer

from secpipe_cli.commands import mcp, projects
from secpipe_cli.context import Context

application: Typer = Typer(
    name="secpipe",
    help="SecPipe AI - Security research orchestration platform.",
)


@application.callback()
def main(
    project_path: Annotated[
        Path,
        Option(
            "--project",
            "-p",
            envvar="SECPIPE_PROJECT__DEFAULT_PATH",
            help="Path to the SecPipe project directory.",
        ),
    ] = Path.cwd(),
    storage_path: Annotated[
        Path,
        Option(
            "--storage",
            envvar="SECPIPE_STORAGE__PATH",
            help="Path to the storage directory.",
        ),
    ] = Path.cwd() / ".secpipe" / "storage",
    context: TyperContext = None,  # type: ignore[assignment]
) -> None:
    """SecPipe AI - Security research orchestration platform.

    Discover and execute MCP hub tools for security research.

    """
    storage = LocalStorage(base_path=storage_path)

    context.obj = Context(
        storage=storage,
        project_path=project_path,
    )


application.add_typer(mcp.application)
application.add_typer(projects.application)


@application.command(
    name="ui",
    help="Launch the SecPipe terminal interface.",
)
def launch_ui() -> None:
    """Launch the interactive SecPipe TUI dashboard.

    Provides a visual dashboard showing AI agent connection status
    and hub server availability, with wizards for setup and configuration.

    """
    from secpipe_cli.tui.app import SecPipeApp

    SecPipeApp().run()
