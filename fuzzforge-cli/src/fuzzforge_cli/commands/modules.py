"""Module management commands for FuzzForge CLI."""

import asyncio
from pathlib import Path
from typing import Annotated, Any

from rich.console import Console
from rich.table import Table
from typer import Argument, Context, Option, Typer

from fuzzforge_cli.context import get_project_path, get_runner

application: Typer = Typer(
    name="modules",
    help="Module management commands.",
)


@application.command(
    help="List available modules.",
    name="list",
)
def list_modules(
    context: Context,
) -> None:
    """List all available modules.

    :param context: Typer context.

    """
    runner = get_runner(context)
    modules = runner.list_modules()

    console = Console()

    if not modules:
        console.print("[yellow]No modules found.[/yellow]")
        console.print(f"  Modules directory: {runner.settings.modules_path}")
        return

    table = Table(title="Available Modules")
    table.add_column("Identifier", style="cyan")
    table.add_column("Available")
    table.add_column("Description")

    for module in modules:
        table.add_row(
            module.identifier,
            "✓" if module.available else "✗",
            module.description or "-",
        )

    console.print(table)


@application.command(
    help="Execute a module.",
    name="run",
)
def run_module(
    context: Context,
    module_identifier: Annotated[
        str,
        Argument(
            help="Identifier of the module to execute.",
        ),
    ],
    assets_path: Annotated[
        Path | None,
        Option(
            "--assets",
            "-a",
            help="Path to input assets.",
        ),
    ] = None,
    config: Annotated[
        str | None,
        Option(
            "--config",
            "-c",
            help="Module configuration as JSON string.",
        ),
    ] = None,
) -> None:
    """Execute a module.

    :param context: Typer context.
    :param module_identifier: Module to execute.
    :param assets_path: Optional path to input assets.
    :param config: Optional JSON configuration.

    """
    import json

    runner = get_runner(context)
    project_path = get_project_path(context)

    configuration: dict[str, Any] | None = None
    if config:
        try:
            configuration = json.loads(config)
        except json.JSONDecodeError as e:
            console = Console()
            console.print(f"[red]✗[/red] Invalid JSON configuration: {e}")
            return

    console = Console()
    console.print(f"[blue]→[/blue] Executing module: {module_identifier}")

    async def execute() -> None:
        result = await runner.execute_module(
            module_identifier=module_identifier,
            project_path=project_path,
            configuration=configuration,
            assets_path=assets_path,
        )

        if result.success:
            console.print(f"[green]✓[/green] Module execution completed")
            console.print(f"  Execution ID: {result.execution_id}")
            console.print(f"  Results: {result.results_path}")
        else:
            console.print(f"[red]✗[/red] Module execution failed")
            console.print(f"  Error: {result.error}")

    asyncio.run(execute())


@application.command(
    help="Show module information.",
    name="info",
)
def module_info(
    context: Context,
    module_identifier: Annotated[
        str,
        Argument(
            help="Identifier of the module.",
        ),
    ],
) -> None:
    """Show information about a specific module.

    :param context: Typer context.
    :param module_identifier: Module to get info for.

    """
    runner = get_runner(context)
    module = runner.get_module_info(module_identifier)

    console = Console()

    if module is None:
        console.print(f"[red]✗[/red] Module not found: {module_identifier}")
        return

    table = Table(title=f"Module: {module.identifier}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Identifier", module.identifier)
    table.add_row("Available", "Yes" if module.available else "No")
    table.add_row("Description", module.description or "-")
    table.add_row("Version", module.version or "-")

    console.print(table)
