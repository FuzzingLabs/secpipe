"""
Main CLI application with improved command structure.
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


import typer
from rich.console import Console
from rich.traceback import install
from typing import Optional, List
import sys

from .commands import (
    workflows,
    workflow_exec,
    findings,
    monitor,
    config as config_cmd,
    ai,
    ingest,
)
from .constants import DEFAULT_VOLUME_MODE
from .fuzzy import enhanced_command_not_found_handler

# Install rich traceback handler
install(show_locals=True)

# Create console for rich output
console = Console()

# Create the main Typer app
app = typer.Typer(
    name="fuzzforge",
    help=(
        "\b\n"
        "[cyan]███████╗██╗   ██╗███████╗███████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗\n"
        "██╔════╝██║   ██║╚══███╔╝╚══███╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝\n"
        "█████╗  ██║   ██║  ███╔╝   ███╔╝ █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  \n"
        "██╔══╝  ██║   ██║ ███╔╝   ███╔╝  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  \n"
        "██║     ╚██████╔╝███████╗███████╗██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗\n"
        "╚═╝      ╚═════╝ ╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝[/cyan]\n\n"
        "🛡️  Security testing workflow orchestration platform"
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={
        # Prevent help text from wrapping so ASCII art stays aligned
        "max_content_width": 200,
        # Keep common help flags
        "help_option_names": ["--help", "-h"],
    },
)

# Create workflow singular command group
workflow_app = typer.Typer(
    name="workflow",
    help="🚀 Execute and manage individual workflows",
    no_args_is_help=False,  # Allow direct execution
)

# Create finding singular command group
finding_app = typer.Typer(
    name="finding",
    help="🔍 View and analyze individual findings",
    no_args_is_help=False,
)


# === Top-level commands ===

@app.command()
def init(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="Project name (defaults to current directory name)"
    ),
    api_url: Optional[str] = typer.Option(
        None, "--api-url", "-u",
        help="FuzzForge API URL (defaults to http://localhost:8000)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Force initialization even if project already exists"
    )
):
    """
    📁 Initialize a new FuzzForge project
    """
    from .commands.init import project
    project(name=name, api_url=api_url, force=force)


@app.command()
def status():
    """
    📊 Show project and latest execution status
    """
    from .commands.status import show_status
    show_status()


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Configuration key"),
    value: Optional[str] = typer.Argument(None, help="Configuration value to set")
):
    """
    ⚙️  Manage configuration (show all, get, or set values)
    """

    if key is None:
        # No arguments: show all config
        config_cmd.show_config(global_config=False)
    elif value is None:
        # Key only: get specific value
        config_cmd.get_config(key=key, global_config=False)
    else:
        # Key and value: set value
        config_cmd.set_config(key=key, value=value, global_config=False)


@app.command()
def clean(
    days: int = typer.Option(
        90, "--days", "-d",
        help="Remove data older than this many days"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show what would be deleted without actually deleting"
    )
):
    """
    🧹 Clean old execution data and findings
    """
    from .database import get_project_db
    from .exceptions import require_project

    try:
        require_project()
        db = get_project_db()
        if not db:
            console.print("❌ No project database found", style="red")
            raise typer.Exit(1)

        if dry_run:
            console.print(f"🔍 [bold]Dry run:[/bold] Would clean data older than {days} days")

        deleted = db.cleanup_old_runs(keep_days=days)

        if not dry_run:
            console.print(f"✅ Cleaned {deleted} old executions", style="green")
        else:
            console.print(f"Would delete {deleted} executions", style="yellow")
    except Exception as e:
        console.print(f"❌ Failed to clean data: {e}", style="red")
        raise typer.Exit(1)


# === Workflow commands (singular) ===

# Add workflow subcommands first (before callback)
workflow_app.command("status")(workflow_exec.workflow_status)
workflow_app.command("history")(workflow_exec.workflow_history)
workflow_app.command("retry")(workflow_exec.retry_workflow)
workflow_app.command("info")(workflows.workflow_info)
workflow_app.command("params")(workflows.workflow_parameters)

@workflow_app.command("run")
def run_workflow(
    workflow: str = typer.Argument(help="Workflow name"),
    target: str = typer.Argument(help="Target path"),
    params: List[str] = typer.Argument(default=None, help="Parameters as key=value pairs"),
    param_file: Optional[str] = typer.Option(
        None, "--param-file", "-f",
        help="JSON file containing workflow parameters"
    ),
    volume_mode: str = typer.Option(
        DEFAULT_VOLUME_MODE, "--volume-mode", "-v",
        help="Volume mount mode: ro (read-only) or rw (read-write)"
    ),
    timeout: Optional[int] = typer.Option(
        None, "--timeout", "-t",
        help="Execution timeout in seconds"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", "-i/-n",
        help="Interactive parameter input for missing required parameters"
    ),
    wait: bool = typer.Option(
        False, "--wait", "-w",
        help="Wait for execution to complete"
    ),
    live: bool = typer.Option(
        False, "--live", "-l",
        help="Start live monitoring after execution (useful for fuzzing workflows)"
    ),
    auto_start: Optional[bool] = typer.Option(
        None, "--auto-start/--no-auto-start",
        help="Automatically start required worker if not running (default: from config)"
    ),
    auto_stop: Optional[bool] = typer.Option(
        None, "--auto-stop/--no-auto-stop",
        help="Automatically stop worker after execution completes (default: from config)"
    ),
    fail_on: Optional[str] = typer.Option(
        None, "--fail-on",
        help="Fail build if findings match SARIF level (error,warning,note,info,all,none). Use with --wait"
    ),
    export_sarif: Optional[str] = typer.Option(
        None, "--export-sarif",
        help="Export SARIF results to file after completion. Use with --wait"
    )
):
    """
    🚀 Execute a security testing workflow

    Use --fail-on with --wait to fail CI builds based on finding severity.
    Use --export-sarif with --wait to export SARIF findings to a file.
    """
    from .commands.workflow_exec import execute_workflow

    execute_workflow(
        workflow=workflow,
        target_path=target,
        params=params,
        param_file=param_file,
        volume_mode=volume_mode,
        timeout=timeout,
        interactive=interactive,
        wait=wait,
        live=live,
        auto_start=auto_start,
        auto_stop=auto_stop,
        fail_on=fail_on,
        export_sarif=export_sarif
    )

@workflow_app.callback()
def workflow_main():
    """
    Execute workflows and manage workflow executions

    Examples:
        fuzzforge workflow security_assessment ./target    # Execute workflow
        fuzzforge workflow status                          # Check latest status
        fuzzforge workflow history                         # Show execution history
    """
    pass


# === Finding commands (singular) ===

@finding_app.command("show")
def show_finding_detail(
    run_id: str = typer.Argument(..., help="Run ID to get finding from"),
    rule_id: str = typer.Option(..., "--rule", "-r", help="Rule ID of the specific finding to show")
):
    """
    🔍 Show detailed information about a specific finding
    """
    from .commands.findings import show_finding
    show_finding(run_id=run_id, rule_id=rule_id)


@finding_app.callback(invoke_without_command=True)
def finding_main(
    ctx: typer.Context,
):
    """
    View and analyze individual findings

    Examples:
        fuzzforge finding                            # Show latest finding
        fuzzforge finding <id>                       # Show specific finding
        fuzzforge finding show <run-id> --rule <id>  # Show specific finding detail
    """
    # Check if a subcommand is being invoked
    if ctx.invoked_subcommand is not None:
        # Let the subcommand handle it
        return

    # Get remaining arguments for direct viewing
    args = ctx.args if hasattr(ctx, 'args') else []
    finding_id = args[0] if args else None

    # Direct viewing: fuzzforge finding [id]
    from .commands.findings import get_findings
    from .database import get_project_db
    from .exceptions import require_project

    try:
        require_project()

        # If no ID provided, get the latest
        if not finding_id:
            db = get_project_db()
            if db:
                recent_runs = db.list_runs(limit=1)
                if recent_runs:
                    finding_id = recent_runs[0].run_id
                    console.print(f"🔍 Using most recent execution: {finding_id}")
                else:
                    console.print("⚠️  No findings found in project database", style="yellow")
                    return
            else:
                console.print("❌ No project database found", style="red")
                return

        get_findings(run_id=finding_id, save=True, format="table")
    except Exception as e:
        console.print(f"❌ Failed to get findings: {e}", style="red")


# === Add command groups ===

# Plural commands (for browsing/listing)
app.add_typer(workflows.app, name="workflows", help="📋 Browse available workflows")
app.add_typer(findings.app, name="findings", help="📋 Browse all findings")

# Singular commands (for actions)
app.add_typer(workflow_app, name="workflow", help="🚀 Execute and manage workflows")
app.add_typer(finding_app, name="finding", help="🔍 View and analyze findings")

# Other command groups
app.add_typer(monitor.app, name="monitor", help="📊 Real-time monitoring")
app.add_typer(ai.app, name="ai", help="🤖 AI integration features")
app.add_typer(ingest.app, name="ingest", help="🧠 Ingest knowledge into AI")

# Help and utility commands
@app.command()
def version():
    """
    📦 Show version information
    """
    from . import __version__
    console.print(f"FuzzForge CLI v{__version__}")
    console.print("Short command: ff")


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v",
        help="Show version information"
    ),
):
    """
    🛡️ FuzzForge CLI - Security testing workflow orchestration platform

    Quick start:
    • ff init                        - Initialize a new project
    • ff workflows                   - See available workflows
    • ff workflow <name> <target>    - Execute a workflow
    """
    if version:
        from . import __version__
        console.print(f"FuzzForge CLI v{__version__}")
        raise typer.Exit()


def main():
    """Main entry point with smart command routing and error handling"""
    # Smart command routing BEFORE Typer processes arguments
    if len(sys.argv) > 1:
        args = sys.argv[1:]


        # Handle finding command with pattern recognition
        if len(args) >= 2 and args[0] == 'finding':
            finding_subcommands = ['show']
            # Skip custom dispatching if help flags are present
            if not any(arg in ['--help', '-h', '--version', '-v'] for arg in args):
                if args[1] not in finding_subcommands:
                    # Direct finding display: ff finding <id>
                    from .commands.findings import get_findings

                    finding_id = args[1]
                    console.print(f"🔍 Displaying finding: {finding_id}")

                    try:
                        get_findings(run_id=finding_id, save=True, format="table")
                        return
                    except Exception as e:
                        console.print(f"❌ Failed to get finding: {e}", style="red")
                        sys.exit(1)

    # Default Typer app handling
    try:
        app()
    except SystemExit as e:
        # Enhanced error handling for command not found
        if hasattr(e, 'code') and e.code != 0 and len(sys.argv) > 1:
            command_parts = sys.argv[1:]
            clean_parts = [part for part in command_parts if not part.startswith('-')]

            if clean_parts:
                main_cmd = clean_parts[0]
                valid_commands = [
                    'init', 'status', 'config', 'clean',
                    'workflows', 'workflow',
                    'findings', 'finding',
                    'monitor', 'ai', 'ingest',
                    'version'
                ]

                if main_cmd not in valid_commands:
                    enhanced_command_not_found_handler(clean_parts)
                    sys.exit(1)
        raise


if __name__ == "__main__":
    main()
