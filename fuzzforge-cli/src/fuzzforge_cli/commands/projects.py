"""Project management commands for FuzzForge CLI."""

from pathlib import Path
from typing import Annotated

from rich.console import Console
from rich.table import Table
from typer import Argument, Context, Option, Typer

from fuzzforge_cli.context import get_project_path, get_runner

application: Typer = Typer(
    name="project",
    help="Project management commands.",
)


@application.command(
    help="Initialize a new FuzzForge project.",
    name="init",
)
def init_project(
    context: Context,
    path: Annotated[
        Path | None,
        Argument(
            help="Path to initialize the project in. Defaults to current directory.",
        ),
    ] = None,
) -> None:
    """Initialize a new FuzzForge project.

    Creates the necessary storage directories for the project.

    :param context: Typer context.
    :param path: Path to initialize (defaults to current directory).

    """
    runner = get_runner(context)
    project_path = path or get_project_path(context)

    storage_path = runner.init_project(project_path)

    console = Console()
    console.print(f"[green]✓[/green] Project initialized at {project_path}")
    console.print(f"  Storage: {storage_path}")


@application.command(
    help="Set project assets.",
    name="assets",
)
def set_assets(
    context: Context,
    assets_path: Annotated[
        Path,
        Argument(
            help="Path to assets file or directory.",
        ),
    ],
) -> None:
    """Set the initial assets for the project.

    :param context: Typer context.
    :param assets_path: Path to assets.

    """
    runner = get_runner(context)
    project_path = get_project_path(context)

    stored_path = runner.set_project_assets(project_path, assets_path)

    console = Console()
    console.print(f"[green]✓[/green] Assets stored from {assets_path}")
    console.print(f"  Location: {stored_path}")


@application.command(
    help="Show project information.",
    name="info",
)
def show_info(
    context: Context,
) -> None:
    """Show information about the current project.

    :param context: Typer context.

    """
    runner = get_runner(context)
    project_path = get_project_path(context)

    executions = runner.list_executions(project_path)
    assets_path = runner.storage.get_project_assets_path(project_path)

    console = Console()
    table = Table(title=f"Project: {project_path.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Path", str(project_path))
    table.add_row("Has Assets", "Yes" if assets_path else "No")
    table.add_row("Assets Path", str(assets_path) if assets_path else "-")
    table.add_row("Executions", str(len(executions)))

    console.print(table)


@application.command(
    help="List all executions.",
    name="executions",
)
def list_executions(
    context: Context,
) -> None:
    """List all executions for the project.

    :param context: Typer context.

    """
    runner = get_runner(context)
    project_path = get_project_path(context)

    executions = runner.list_executions(project_path)

    console = Console()

    if not executions:
        console.print("[yellow]No executions found.[/yellow]")
        return

    table = Table(title="Executions")
    table.add_column("ID", style="cyan")
    table.add_column("Has Results")

    for exec_id in executions:
        has_results = runner.get_execution_results(project_path, exec_id) is not None
        table.add_row(exec_id, "✓" if has_results else "-")

    console.print(table)


@application.command(
    help="Get execution results.",
    name="results",
)
def get_results(
    context: Context,
    execution_id: Annotated[
        str,
        Argument(
            help="Execution ID to get results for.",
        ),
    ],
    extract_to: Annotated[
        Path | None,
        Option(
            "--extract",
            "-x",
            help="Extract results to this directory.",
        ),
    ] = None,
) -> None:
    """Get results for a specific execution.

    :param context: Typer context.
    :param execution_id: Execution ID.
    :param extract_to: Optional directory to extract to.

    """
    runner = get_runner(context)
    project_path = get_project_path(context)

    results_path = runner.get_execution_results(project_path, execution_id)

    console = Console()

    if results_path is None:
        console.print(f"[red]✗[/red] No results found for execution {execution_id}")
        return

    console.print(f"[green]✓[/green] Results: {results_path}")

    if extract_to:
        extracted = runner.extract_results(results_path, extract_to)
        console.print(f"  Extracted to: {extracted}")
