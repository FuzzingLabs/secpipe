"""Cognee ingestion commands for FuzzForge CLI."""
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.


from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.prompt import Confirm

from ..config import ProjectConfigManager
from ..ingest_utils import collect_ingest_files

console = Console()
app = typer.Typer(
    name="ingest",
    help="Ingest files or directories into the Cognee knowledge graph for the current project",
    invoke_without_command=True,
)


@app.callback()
def ingest_callback(
    ctx: typer.Context,
    path: Optional[Path] = typer.Argument(
        None,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="File or directory to ingest (defaults to current directory)",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Recursively ingest directories",
    ),
    file_types: Optional[List[str]] = typer.Option(
        None,
        "--file-types",
        "-t",
        help="File extensions to include (e.g. --file-types .py --file-types .js)",
    ),
    exclude: Optional[List[str]] = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Glob patterns to exclude",
    ),
    dataset: Optional[str] = typer.Option(
        None,
        "--dataset",
        "-d",
        help="Dataset name to ingest into",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-ingestion and skip confirmation",
    ),
):
    """Entry point for `fuzzforge ingest` when no subcommand is provided."""
    if ctx.invoked_subcommand:
        return

    try:
        config = ProjectConfigManager()
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if not config.is_initialized():
        console.print("[red]Error: FuzzForge project not initialized. Run 'ff init' first.[/red]")
        raise typer.Exit(1)

    config.setup_cognee_environment()
    if os.getenv("FUZZFORGE_DEBUG", "0") == "1":
        console.print(
            "[dim]Cognee directories:\n"
            f"  DATA: {os.getenv('COGNEE_DATA_ROOT', 'unset')}\n"
            f"  SYSTEM: {os.getenv('COGNEE_SYSTEM_ROOT', 'unset')}\n"
            f"  USER: {os.getenv('COGNEE_USER_ID', 'unset')}\n",
        )
    project_context = config.get_project_context()

    target_path = path or Path.cwd()
    dataset_name = dataset or f"{project_context['project_name']}_codebase"

    try:
        import cognee  # noqa: F401  # Just to validate installation
    except ImportError as exc:
        console.print("[red]Cognee is not installed.[/red]")
        console.print("Install with: pip install 'cognee[all]' litellm")
        raise typer.Exit(1) from exc

    console.print(f"[bold]🔍 Ingesting {target_path} into Cognee knowledge graph[/bold]")
    console.print(
        f"Project: [cyan]{project_context['project_name']}[/cyan] "
        f"(ID: [dim]{project_context['project_id']}[/dim])"
    )
    console.print(f"Dataset: [cyan]{dataset_name}[/cyan]")
    console.print(f"Tenant: [dim]{project_context['tenant_id']}[/dim]")

    if not force:
        confirm_message = f"Ingest {target_path} into knowledge graph for this project?"
        if not Confirm.ask(confirm_message, console=console):
            console.print("[yellow]Ingestion cancelled[/yellow]")
            raise typer.Exit(0)

    try:
        asyncio.run(
            _run_ingestion(
                config=config,
                path=target_path.resolve(),
                recursive=recursive,
                file_types=file_types,
                exclude=exclude,
                dataset=dataset_name,
                force=force,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Ingestion cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as exc:  # pragma: no cover - rich reporting
        console.print(f"[red]Failed to ingest:[/red] {exc}")
        raise typer.Exit(1) from exc


async def _run_ingestion(
    *,
    config: ProjectConfigManager,
    path: Path,
    recursive: bool,
    file_types: Optional[List[str]],
    exclude: Optional[List[str]],
    dataset: str,
    force: bool,
) -> None:
    """Perform the actual ingestion work."""
    from fuzzforge_ai.cognee_service import CogneeService

    cognee_service = CogneeService(config)
    await cognee_service.initialize()

    # Always skip internal bookkeeping directories
    exclude_patterns = list(exclude or [])
    default_excludes = {
        ".fuzzforge/**",
        ".git/**",
    }
    added_defaults = []
    for pattern in default_excludes:
        if pattern not in exclude_patterns:
            exclude_patterns.append(pattern)
            added_defaults.append(pattern)

    if added_defaults and os.getenv("FUZZFORGE_DEBUG", "0") == "1":
        console.print(
            "[dim]Auto-excluding paths: {patterns}[/dim]".format(
                patterns=", ".join(added_defaults)
            )
        )

    try:
        files_to_ingest = collect_ingest_files(path, recursive, file_types, exclude_patterns)
    except Exception as exc:
        console.print(f"[red]Failed to collect files:[/red] {exc}")
        return

    if not files_to_ingest:
        console.print("[yellow]No files found to ingest[/yellow]")
        return

    console.print(f"Found [green]{len(files_to_ingest)}[/green] files to ingest")

    if force:
        console.print("Cleaning existing data for this project...")
        try:
            await cognee_service.clear_data(confirm=True)
        except Exception as exc:
            console.print(f"[yellow]Warning:[/yellow] Could not clean existing data: {exc}")

    console.print("Adding files to Cognee...")
    valid_file_paths = []
    for file_path in files_to_ingest:
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                fh.read(1)
            valid_file_paths.append(file_path)
            console.print(f"  ✓ {file_path}")
        except (UnicodeDecodeError, PermissionError) as exc:
            console.print(f"[yellow]Skipping {file_path}: {exc}[/yellow]")

    if not valid_file_paths:
        console.print("[yellow]No readable files found to ingest[/yellow]")
        return

    results = await cognee_service.ingest_files(valid_file_paths, dataset)

    console.print(
        f"[green]✅ Successfully ingested {results['success']} files into knowledge graph[/green]"
    )
    if results["failed"]:
        console.print(
            f"[yellow]⚠️  Skipped {results['failed']} files due to errors[/yellow]"
        )

    try:
        insights = await cognee_service.search_insights(
            query=f"What insights can you provide about the {dataset} dataset?",
            dataset=dataset,
        )
        if insights:
            console.print(f"\n[bold]📊 Generated {len(insights)} insights:[/bold]")
            for index, insight in enumerate(insights[:3], 1):
                console.print(f"  {index}. {insight}")
            if len(insights) > 3:
                console.print(f"  ... and {len(insights) - 3} more")

        chunks = await cognee_service.search_chunks(
            query=f"functions classes methods in {dataset}",
            dataset=dataset,
        )
        if chunks:
            console.print(
                f"\n[bold]🔍 Sample searchable content ({len(chunks)} chunks found):[/bold]"
            )
            for index, chunk in enumerate(chunks[:2], 1):
                preview = chunk[:100] + "..." if len(chunk) > 100 else chunk
                console.print(f"  {index}. {preview}")
    except Exception:
        # Best-effort stats — ignore failures here
        pass
