"""FuzzForge CLI application."""

from pathlib import Path
from typing import Annotated

from typer import Context as TyperContext
from typer import Option, Typer

from fuzzforge_cli.commands import mcp, projects
from fuzzforge_cli.context import Context
from fuzzforge_mcp.storage import LocalStorage

application: Typer = Typer(
    name="fuzzforge",
    help="FuzzForge AI - Security research orchestration platform.",
)


@application.callback()
def main(
    project_path: Annotated[
        Path,
        Option(
            "--project",
            "-p",
            envvar="FUZZFORGE_PROJECT__DEFAULT_PATH",
            help="Path to the FuzzForge project directory.",
        ),
    ] = Path.cwd(),
    storage_path: Annotated[
        Path,
        Option(
            "--storage",
            envvar="FUZZFORGE_STORAGE__PATH",
            help="Path to the storage directory.",
        ),
    ] = Path.home() / ".fuzzforge" / "storage",
    context: TyperContext = None,  # type: ignore[assignment]
) -> None:
    """FuzzForge AI - Security research orchestration platform.

    Discover and execute MCP hub tools for security research.

    """
    storage = LocalStorage(storage_path=storage_path)

    context.obj = Context(
        storage=storage,
        project_path=project_path,
    )


application.add_typer(mcp.application)
application.add_typer(projects.application)
