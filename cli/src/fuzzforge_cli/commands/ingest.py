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
from ..cognee_api import CogneeApiClient, CogneeApiError
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
        storage_backend = os.getenv("COGNEE_STORAGE_BACKEND", "local")
        console.print(
            "[dim]Cognee directories:\n"
            f"  DATA: {os.getenv('COGNEE_DATA_ROOT', 'unset')}\n"
            f"  SYSTEM: {os.getenv('COGNEE_SYSTEM_ROOT', 'unset')}\n"
            f"  USER: {os.getenv('COGNEE_USER_ID', 'unset')}\n"
            f"  STORAGE: {storage_backend}\n",
        )
    project_context = config.get_project_context()

    target_path = path or Path.cwd()
    dataset_name = dataset or f"{project_context['project_id']}_codebase"

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
    cognee_cfg = config.get_cognee_config()
    service_url = (
        cognee_cfg.get("service_url")
        or os.getenv("COGNEE_SERVICE_URL")
        or "http://localhost:18000"
    )
    service_email = os.getenv("COGNEE_SERVICE_EMAIL") or cognee_cfg.get("service_email")
    service_password = os.getenv("COGNEE_SERVICE_PASSWORD") or cognee_cfg.get("service_password")

    if not service_email or not service_password:
        console.print(
            "[red]Missing Cognee service credentials.[/red] Run `ff init` again or set "
            "COGNEE_SERVICE_EMAIL / COGNEE_SERVICE_PASSWORD in .fuzzforge/.env."
        )
        return

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
        console.print(
            "[yellow]Warning:[/yellow] Force re-ingest is not yet supported for the remote Cognee service."
        )

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

    async with CogneeApiClient(
        service_url,
        email=service_email,
        password=service_password,
    ) as client:
        try:
            await client.ensure_authenticated()
        except CogneeApiError as exc:
            console.print(f"[red]Cognee authentication failed:[/red] {exc}")
            return
        except Exception as exc:
            console.print(f"[red]Cognee authentication error:[/red] {exc}")
            return

        try:
            await client.add_files(valid_file_paths, dataset)
            await client.cognify([dataset])
        except CogneeApiError as exc:
            console.print(f"[red]Cognee API error:[/red] {exc}")
            return
        except Exception as exc:
            console.print(f"[red]Unexpected Cognee error:[/red] {exc}")
            return

        console.print(
            f"[green]✅ Successfully ingested {len(valid_file_paths)} files into knowledge graph[/green]"
        )

        try:
            insights = await client.search(
                query=f"What insights can you provide about the {dataset} dataset?",
                search_type="INSIGHTS",
                datasets=[dataset],
            )
            insight_list = insights if isinstance(insights, list) else insights.get("results", [])
            if insight_list:
                console.print(f"\n[bold]📊 Generated {len(insight_list)} insights:[/bold]")
                for index, insight in enumerate(insight_list[:3], 1):
                    console.print(f"  {index}. {insight}")
                if len(insight_list) > 3:
                    console.print(f"  ... and {len(insight_list) - 3} more")

            chunks = await client.search(
                query=f"functions classes methods in {dataset}",
                search_type="CHUNKS",
                datasets=[dataset],
                top_k=5,
            )
            chunk_list = chunks if isinstance(chunks, list) else chunks.get("results", [])
            if chunk_list:
                console.print(
                    f"\n[bold]🔍 Sample searchable content ({len(chunk_list)} chunks found):[/bold]"
                )
                for index, chunk in enumerate(chunk_list[:2], 1):
                    text = str(chunk)
                    preview = text[:100] + "..." if len(text) > 100 else text
                    console.print(f"  {index}. {preview}")
        except Exception:
            pass
