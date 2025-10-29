"""
Worker management commands for FuzzForge CLI.

Provides commands to start, stop, and list Temporal workers.
"""
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

import subprocess
import sys
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from typing import Optional

from ..worker_manager import WorkerManager

console = Console()
app = typer.Typer(
    name="worker",
    help="🔧 Manage Temporal workers",
    no_args_is_help=True,
)


@app.command("stop")
def stop_workers(
    all: bool = typer.Option(
        False, "--all",
        help="Stop all workers (default behavior, flag for clarity)"
    )
):
    """
    🛑 Stop all running FuzzForge workers.

    This command stops all worker containers using the proper Docker Compose
    profile flag to ensure workers are actually stopped (since they're in profiles).

    Examples:
        $ ff worker stop
        $ ff worker stop --all
    """
    try:
        worker_mgr = WorkerManager()
        success = worker_mgr.stop_all_workers()

        if success:
            sys.exit(0)
        else:
            console.print("⚠️  Some workers may not have stopped properly", style="yellow")
            sys.exit(1)

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


@app.command("list")
def list_workers(
    all: bool = typer.Option(
        False, "--all", "-a",
        help="Show all workers (including stopped)"
    )
):
    """
    📋 List FuzzForge workers and their status.

    By default, shows only running workers. Use --all to see all workers.

    Examples:
        $ ff worker list
        $ ff worker list --all
    """
    try:
        # Get list of running workers
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=fuzzforge-worker-",
             "--format", "{{.Names}}\t{{.Status}}\t{{.RunningFor}}"],
            capture_output=True,
            text=True,
            check=False
        )

        running_workers = []
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                parts = line.split('\t')
                if len(parts) >= 3:
                    running_workers.append({
                        "name": parts[0].replace("fuzzforge-worker-", ""),
                        "status": "Running",
                        "uptime": parts[2]
                    })

        # If --all, also get stopped workers
        stopped_workers = []
        if all:
            result_all = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=fuzzforge-worker-",
                 "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                check=False
            )

            all_worker_names = set()
            for line in result_all.stdout.strip().splitlines():
                parts = line.split('\t')
                if len(parts) >= 2:
                    worker_name = parts[0].replace("fuzzforge-worker-", "")
                    all_worker_names.add(worker_name)
                    # If not running, it's stopped
                    if not any(w["name"] == worker_name for w in running_workers):
                        stopped_workers.append({
                            "name": worker_name,
                            "status": "Stopped",
                            "uptime": "-"
                        })

        # Display results
        if not running_workers and not stopped_workers:
            console.print("ℹ️  No workers found", style="cyan")
            console.print("\n💡 Start a worker with: [cyan]docker compose up -d worker-<name>[/cyan]")
            console.print("   Or run a workflow, which auto-starts workers: [cyan]ff workflow run <workflow> <target>[/cyan]")
            return

        # Create table
        table = Table(title="FuzzForge Workers", show_header=True, header_style="bold cyan")
        table.add_column("Worker", style="cyan", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("Uptime", style="dim")

        # Add running workers
        for worker in running_workers:
            table.add_row(
                worker["name"],
                f"[green]●[/green] {worker['status']}",
                worker["uptime"]
            )

        # Add stopped workers if --all
        for worker in stopped_workers:
            table.add_row(
                worker["name"],
                f"[red]●[/red] {worker['status']}",
                worker["uptime"]
            )

        console.print(table)

        # Summary
        if running_workers:
            console.print(f"\n✅ {len(running_workers)} worker(s) running")
        if stopped_workers:
            console.print(f"⏹️  {len(stopped_workers)} worker(s) stopped")

    except Exception as e:
        console.print(f"❌ Error listing workers: {e}", style="red")
        sys.exit(1)


@app.command("start")
def start_worker(
    name: str = typer.Argument(
        ...,
        help="Worker name (e.g., 'python', 'android', 'secrets')"
    ),
    build: bool = typer.Option(
        False, "--build",
        help="Rebuild worker image before starting"
    )
):
    """
    🚀 Start a specific worker.

    The worker name should be the vertical name (e.g., 'python', 'android', 'rust').

    Examples:
        $ ff worker start python
        $ ff worker start android --build
    """
    try:
        service_name = f"worker-{name}"

        console.print(f"🚀 Starting worker: [cyan]{service_name}[/cyan]")

        # Build docker compose command
        cmd = ["docker", "compose", "up", "-d"]
        if build:
            cmd.append("--build")
        cmd.append(service_name)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            console.print(f"✅ Worker [cyan]{service_name}[/cyan] started successfully")
        else:
            console.print(f"❌ Failed to start worker: {result.stderr}", style="red")
            console.print(
                f"\n💡 Try manually: [yellow]docker compose up -d {service_name}[/yellow]",
                style="dim"
            )
            sys.exit(1)

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    app()
