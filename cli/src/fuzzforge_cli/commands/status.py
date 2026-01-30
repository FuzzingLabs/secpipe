"""
Status command for showing project and API information.
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


from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ..config import get_project_config, FuzzForgeConfig
from ..database import get_project_db
from fuzzforge_sdk import FuzzForgeClient

console = Console()


def show_status():
    """Show comprehensive project and API status"""
    current_dir = Path.cwd()
    fuzzforge_dir = current_dir / ".fuzzforge"

    # Project status
    console.print("\n📊 [bold]FuzzForge Project Status[/bold]\n")

    if not fuzzforge_dir.exists():
        console.print(
            Panel.fit(
                "❌ No FuzzForge project found in current directory\n\n"
                "Run [bold cyan]ff init[/bold cyan] to initialize a project",
                title="Project Status",
                box=box.ROUNDED
            )
        )
        return

    # Load project configuration
    config = get_project_config()
    if not config:
        config = FuzzForgeConfig()

    # Project info table
    project_table = Table(show_header=False, box=box.SIMPLE)
    project_table.add_column("Property", style="bold cyan")
    project_table.add_column("Value")

    project_table.add_row("Project Name", config.project.name)
    project_table.add_row("Location", str(current_dir))
    project_table.add_row("API URL", config.project.api_url)
    project_table.add_row("Default Timeout", f"{config.project.default_timeout}s")

    console.print(
        Panel.fit(
            project_table,
            title="✅ Project Information",
            box=box.ROUNDED
        )
    )

    # Database status
    db = get_project_db()
    if db:
        try:
            stats = db.get_stats()
            db_table = Table(show_header=False, box=box.SIMPLE)
            db_table.add_column("Metric", style="bold cyan")
            db_table.add_column("Count", justify="right")

            db_table.add_row("Total Runs", str(stats["total_runs"]))
            db_table.add_row("Total Findings", str(stats["total_findings"]))
            db_table.add_row("Total Crashes", str(stats["total_crashes"]))
            db_table.add_row("Runs (Last 7 days)", str(stats["runs_last_7_days"]))

            if stats["runs_by_status"]:
                db_table.add_row("", "")  # Spacer
                for status, count in stats["runs_by_status"].items():
                    status_emoji = {
                        "completed": "✅",
                        "running": "🔄",
                        "failed": "❌",
                        "queued": "⏳",
                        "cancelled": "⏹️"
                    }.get(status, "📋")
                    db_table.add_row(f"{status_emoji} {status.title()}", str(count))

            console.print(
                Panel.fit(
                    db_table,
                    title="🗄️  Database Statistics",
                    box=box.ROUNDED
                )
            )
        except Exception as e:
            console.print(f"⚠️  Database error: {e}", style="yellow")

    # API status
    console.print("\n🔗 [bold]API Connectivity[/bold]")
    try:
        with FuzzForgeClient(base_url=config.get_api_url(), timeout=10.0) as client:
            api_status = client.get_api_status()
            workflows = client.list_workflows()

            api_table = Table(show_header=False, box=box.SIMPLE)
            api_table.add_column("Property", style="bold cyan")
            api_table.add_column("Value")

            api_table.add_row("Status", "✅ Connected")
            api_table.add_row("Service", f"{api_status.name} v{api_status.version}")
            api_table.add_row("Workflows", str(len(workflows)))

            console.print(
                Panel.fit(
                    api_table,
                    title="✅ API Status",
                    box=box.ROUNDED
                )
            )

            # Show available workflows
            if workflows:
                workflow_table = Table(box=box.SIMPLE_HEAD)
                workflow_table.add_column("Name", style="bold")
                workflow_table.add_column("Version", justify="center")
                workflow_table.add_column("Description")

                for workflow in workflows[:10]:  # Limit to first 10
                    workflow_table.add_row(
                        workflow.name,
                        workflow.version,
                        workflow.description[:60] + "..." if len(workflow.description) > 60 else workflow.description
                    )

                if len(workflows) > 10:
                    workflow_table.add_row("...", "...", f"and {len(workflows) - 10} more workflows")

                console.print(
                    Panel.fit(
                        workflow_table,
                        title=f"🔧 Available Workflows ({len(workflows)})",
                        box=box.ROUNDED
                    )
                )

    except Exception as e:
        console.print(
            Panel.fit(
                f"❌ Failed to connect to API\n\n"
                f"Error: {str(e)}\n\n"
                f"API URL: {config.get_api_url()}\n\n"
                "Check that the FuzzForge API is running and accessible.",
                title="❌ API Connection Failed",
                box=box.ROUNDED
            )
        )