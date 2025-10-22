"""
Workflow execution and management commands.
Replaces the old 'runs' terminology with cleaner workflow-centric commands.
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


import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box

from ..config import get_project_config, FuzzForgeConfig
from ..database import get_project_db, ensure_project_db, RunRecord
from ..exceptions import (
    handle_error, retry_on_network_error, safe_json_load, require_project,
    ValidationError, DatabaseError
)
from ..validation import (
    validate_run_id, validate_workflow_name, validate_target_path,
    validate_parameters, validate_timeout
)
from ..progress import step_progress
from ..constants import (
    STATUS_EMOJIS, MAX_RUN_ID_DISPLAY_LENGTH, DEFAULT_VOLUME_MODE,
    PROGRESS_STEP_DELAYS, MAX_RETRIES, RETRY_DELAY, POLL_INTERVAL
)
from ..worker_manager import WorkerManager
from fuzzforge_sdk import FuzzForgeClient, WorkflowSubmission

console = Console()
app = typer.Typer()


@retry_on_network_error(max_retries=MAX_RETRIES, delay=RETRY_DELAY)
def get_client() -> FuzzForgeClient:
    """Get configured FuzzForge client with retry on network errors"""
    config = get_project_config() or FuzzForgeConfig()
    return FuzzForgeClient(base_url=config.get_api_url(), timeout=config.get_timeout())


def status_emoji(status: str) -> str:
    """Get emoji for execution status"""
    return STATUS_EMOJIS.get(status.lower(), STATUS_EMOJIS["unknown"])


def should_fail_build(sarif_data: Dict[str, Any], fail_on: str) -> bool:
    """
    Check if findings warrant build failure based on SARIF severity levels.

    Args:
        sarif_data: SARIF format findings data
        fail_on: Comma-separated SARIF levels (error,warning,note,info,all,none)

    Returns:
        True if build should fail, False otherwise
    """
    if fail_on == "none":
        return False

    # Parse fail_on parameter - accept SARIF levels
    if fail_on == "all":
        check_levels = {"error", "warning", "note", "info"}
    else:
        check_levels = {s.strip().lower() for s in fail_on.split(",")}

    # Validate levels
    valid_levels = {"error", "warning", "note", "info", "none"}
    invalid = check_levels - valid_levels
    if invalid:
        console.print(f"⚠️  Invalid SARIF levels: {', '.join(invalid)}", style="yellow")
        console.print("Valid levels: error, warning, note, info, all, none")

    # Check SARIF results
    runs = sarif_data.get("runs", [])
    if not runs:
        return False

    results = runs[0].get("results", [])
    for result in results:
        level = result.get("level", "note")  # SARIF default is "note"
        if level in check_levels:
            return True

    return False


def parse_inline_parameters(params: List[str]) -> Dict[str, Any]:
    """Parse inline key=value parameters using improved validation"""
    return validate_parameters(params)


def execute_workflow_submission(
    client: FuzzForgeClient,
    workflow: str,
    target_path: str,
    parameters: Dict[str, Any],
    volume_mode: str,
    timeout: Optional[int],
    interactive: bool
) -> Any:
    """Handle the workflow submission process with file upload"""
    # Get workflow metadata for parameter validation
    console.print(f"🔧 Getting workflow information for: {workflow}")
    workflow_meta = client.get_workflow_metadata(workflow)

    # Interactive parameter input
    if interactive and workflow_meta.parameters.get("properties"):
        properties = workflow_meta.parameters.get("properties", {})
        required_params = set(workflow_meta.parameters.get("required", []))

        missing_required = required_params - set(parameters.keys())

        if missing_required:
            console.print(f"\n📝 [bold]Missing required parameters:[/bold] {', '.join(missing_required)}")
            console.print("Please provide values:\n")

            for param_name in missing_required:
                param_schema = properties.get(param_name, {})
                description = param_schema.get("description", "")
                param_type = param_schema.get("type", "string")

                prompt_text = f"{param_name}"
                if description:
                    prompt_text += f" ({description})"
                prompt_text += f" [{param_type}]"

                while True:
                    user_input = Prompt.ask(prompt_text, console=console)

                    try:
                        if param_type == "integer":
                            parameters[param_name] = int(user_input)
                        elif param_type == "number":
                            parameters[param_name] = float(user_input)
                        elif param_type == "boolean":
                            parameters[param_name] = user_input.lower() in ("true", "yes", "1", "on")
                        elif param_type == "array":
                            parameters[param_name] = [item.strip() for item in user_input.split(",") if item.strip()]
                        else:
                            parameters[param_name] = user_input
                        break
                    except ValueError as e:
                        console.print(f"❌ Invalid {param_type}: {e}", style="red")

    # Note: volume_mode is no longer used (Temporal uses MinIO storage)

    # Show submission summary
    console.print("\n🎯 [bold]Executing workflow:[/bold]")
    console.print(f"   Workflow: {workflow}")
    console.print(f"   Target: {target_path}")
    console.print(f"   Volume Mode: {volume_mode}")
    if parameters:
        console.print(f"   Parameters: {len(parameters)} provided")
    if timeout:
        console.print(f"   Timeout: {timeout}s")

    # Check if target path exists locally
    target_path_obj = Path(target_path)
    use_upload = target_path_obj.exists()

    if use_upload:
        # Show file/directory info
        if target_path_obj.is_dir():
            num_files = sum(1 for _ in target_path_obj.rglob("*") if _.is_file())
            console.print(f"   Upload: Directory with {num_files} files")
        else:
            size_mb = target_path_obj.stat().st_size / (1024 * 1024)
            console.print(f"   Upload: File ({size_mb:.2f} MB)")
    else:
        console.print("   [yellow]⚠️  Warning: Target path does not exist locally[/yellow]")
        console.print("   [yellow]   Attempting to use path-based submission (backend must have access)[/yellow]")

    # Only ask for confirmation in interactive mode
    if interactive:
        if not Confirm.ask("\nExecute workflow?", default=True, console=console):
            console.print("❌ Execution cancelled", style="yellow")
            raise typer.Exit(0)
    else:
        console.print("\n🚀 Executing workflow...")

    # Submit the workflow with enhanced progress
    console.print(f"\n🚀 Executing workflow: [bold yellow]{workflow}[/bold yellow]")

    if use_upload:
        # Use new upload-based submission
        steps = [
            "Validating workflow configuration",
            "Creating tarball (if directory)",
            "Uploading target to backend",
            "Starting workflow execution",
            "Initializing execution environment"
        ]

        with step_progress(steps, f"Executing {workflow}") as progress:
            progress.next_step()  # Validating
            time.sleep(PROGRESS_STEP_DELAYS["validating"])

            progress.next_step()  # Creating tarball
            time.sleep(PROGRESS_STEP_DELAYS["connecting"])

            progress.next_step()  # Uploading
            # Use the new upload method
            response = client.submit_workflow_with_upload(
                workflow_name=workflow,
                target_path=target_path,
                parameters=parameters,
                timeout=timeout
            )
            time.sleep(PROGRESS_STEP_DELAYS["uploading"])

            progress.next_step()  # Starting
            time.sleep(PROGRESS_STEP_DELAYS["creating"])

            progress.next_step()  # Initializing
            time.sleep(PROGRESS_STEP_DELAYS["initializing"])

            progress.complete("Workflow started successfully!")
    else:
        # Fall back to path-based submission (for backward compatibility)
        steps = [
            "Validating workflow configuration",
            "Connecting to FuzzForge API",
            "Submitting workflow parameters",
            "Creating workflow deployment",
            "Initializing execution environment"
        ]

        with step_progress(steps, f"Executing {workflow}") as progress:
            progress.next_step()  # Validating
            time.sleep(PROGRESS_STEP_DELAYS["validating"])

            progress.next_step()  # Connecting
            time.sleep(PROGRESS_STEP_DELAYS["connecting"])

            progress.next_step()  # Submitting
            submission = WorkflowSubmission(
                target_path=target_path,
                volume_mode=volume_mode,
                parameters=parameters,
                timeout=timeout
            )
            response = client.submit_workflow(workflow, submission)
            time.sleep(PROGRESS_STEP_DELAYS["uploading"])

            progress.next_step()  # Creating deployment
            time.sleep(PROGRESS_STEP_DELAYS["creating"])

            progress.next_step()  # Initializing
            time.sleep(PROGRESS_STEP_DELAYS["initializing"])

            progress.complete("Workflow started successfully!")

    return response


# Main workflow execution command (replaces 'runs submit')
@app.command(name="exec", hidden=True)  # Hidden because it will be called from main workflow command
def execute_workflow(
    workflow: str = typer.Argument(..., help="Workflow name to execute"),
    target_path: str = typer.Argument(..., help="Path to analyze"),
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
        help="Fail build if findings match severity (critical,high,medium,low,all,none). Use with --wait"
    ),
    export_sarif: Optional[str] = typer.Option(
        None, "--export-sarif",
        help="Export SARIF results to file after completion. Use with --wait"
    )
):
    """
    🚀 Execute a workflow on a target

    Use --live for fuzzing workflows to see real-time progress.
    Use --wait to wait for completion without live dashboard.
    Use --fail-on with --wait to fail CI builds based on finding severity.
    Use --export-sarif with --wait to export SARIF findings to a file.
    """
    try:
        # Validate inputs
        validate_workflow_name(workflow)
        target_path_obj = validate_target_path(target_path, must_exist=True)
        target_path = str(target_path_obj.absolute())
        validate_timeout(timeout)

        # Ensure we're in a project directory
        require_project()
    except Exception as e:
        handle_error(e, "validating inputs")

    # Parse parameters
    parameters = {}

    # Load from param file
    if param_file:
        try:
            file_params = safe_json_load(param_file)
            if isinstance(file_params, dict):
                parameters.update(file_params)
            else:
                raise ValidationError("parameter file", param_file, "a JSON object")
        except Exception as e:
            handle_error(e, "loading parameter file")

    # Parse inline parameters
    if params:
        try:
            inline_params = parse_inline_parameters(params)
            parameters.update(inline_params)
        except Exception as e:
            handle_error(e, "parsing parameters")

    # Get config for worker management settings
    config = get_project_config() or FuzzForgeConfig()
    should_auto_start = auto_start if auto_start is not None else config.workers.auto_start_workers
    should_auto_stop = auto_stop if auto_stop is not None else config.workers.auto_stop_workers

    worker_service = None  # Track for cleanup
    worker_mgr = None
    wait_completed = False  # Track if wait completed successfully

    try:
        with get_client() as client:
            # Get worker information for this workflow
            try:
                console.print(f"🔍 Checking worker requirements for: {workflow}")
                worker_info = client.get_workflow_worker_info(workflow)

                # Initialize worker manager
                compose_file = config.workers.docker_compose_file
                worker_mgr = WorkerManager(
                    compose_file=Path(compose_file) if compose_file else None,
                    startup_timeout=config.workers.worker_startup_timeout
                )

                # Ensure worker is running
                worker_service = worker_info.get("worker_service", f"worker-{worker_info['vertical']}")
                if not worker_mgr.ensure_worker_running(worker_info, auto_start=should_auto_start):
                    console.print(
                        f"❌ Worker not available: {worker_info['vertical']}",
                        style="red"
                    )
                    console.print(
                        f"💡 Start the worker manually: docker compose up -d {worker_service}"
                    )
                    raise typer.Exit(1)

            except typer.Exit:
                raise  # Re-raise Exit to preserve exit code
            except Exception as e:
                # If we can't get worker info, warn but continue (might be old backend)
                console.print(
                    f"⚠️  Could not check worker requirements: {e}",
                    style="yellow"
                )
                console.print(
                    "   Continuing without worker management...",
                    style="yellow"
                )

            response = execute_workflow_submission(
                client, workflow, target_path, parameters,
                volume_mode, timeout, interactive
            )

            console.print("✅ Workflow execution started!", style="green")
            console.print(f"   Execution ID: [bold cyan]{response.run_id}[/bold cyan]")
            console.print(f"   Status: {status_emoji(response.status)} {response.status}")

            # Save to database
            try:
                db = ensure_project_db()
                run_record = RunRecord(
                    run_id=response.run_id,
                    workflow=workflow,
                    status=response.status,
                    target_path=target_path,
                    parameters=parameters,
                    created_at=datetime.now()
                )
                db.save_run(run_record)
            except Exception as e:
                # Don't fail the whole operation if database save fails
                console.print(f"⚠️  Failed to save execution to database: {e}", style="yellow")

            console.print(f"\n💡 Monitor progress: [bold cyan]fuzzforge monitor live {response.run_id}[/bold cyan]")
            console.print(f"💡 Check status: [bold cyan]fuzzforge workflow status {response.run_id}[/bold cyan]")

            # Suggest --live for fuzzing workflows
            if not live and not wait and "fuzzing" in workflow.lower():
                console.print(f"💡 Next time try: [bold cyan]fuzzforge workflow {workflow} {target_path} --live[/bold cyan] for real-time monitoring", style="dim")

            # Start live monitoring if requested
            if live:
                # Check if this is a fuzzing workflow to show appropriate messaging
                is_fuzzing = "fuzzing" in workflow.lower()
                if is_fuzzing:
                    console.print("\n📺 Starting live fuzzing monitor...")
                    console.print("💡 You'll see real-time crash discovery, execution stats, and coverage data.")
                else:
                    console.print("\n📺 Starting live monitoring...")

                console.print("Press Ctrl+C to stop monitoring (execution continues in background).\n")

                try:
                    from ..commands.monitor import live_monitor
                    # Import monitor command and run it
                    live_monitor(response.run_id, refresh=3)
                except KeyboardInterrupt:
                    console.print("\n⏹️  Live monitoring stopped (execution continues in background)", style="yellow")
                except Exception as e:
                    console.print(f"⚠️  Failed to start live monitoring: {e}", style="yellow")
                    console.print(f"💡 You can still monitor manually: [bold cyan]fuzzforge monitor live {response.run_id}[/bold cyan]")

            # Wait for completion if requested
            elif wait:
                console.print("\n⏳ Waiting for execution to complete...")
                try:
                    final_status = client.wait_for_completion(response.run_id, poll_interval=POLL_INTERVAL)

                    # Update database
                    try:
                        db.update_run_status(
                            response.run_id,
                            final_status.status,
                            completed_at=datetime.now() if final_status.is_completed else None
                        )
                    except Exception as e:
                        console.print(f"⚠️  Failed to update database: {e}", style="yellow")

                    console.print(f"🏁 Execution completed with status: {status_emoji(final_status.status)} {final_status.status}")
                    wait_completed = True  # Mark wait as completed

                    if final_status.is_completed:
                        # Export SARIF if requested
                        if export_sarif:
                            try:
                                console.print("\n📤 Exporting SARIF results...")
                                findings = client.get_run_findings(response.run_id)
                                output_path = Path(export_sarif)
                                with open(output_path, 'w') as f:
                                    json.dump(findings.sarif, f, indent=2)
                                console.print(f"✅ SARIF exported to: [bold cyan]{output_path}[/bold cyan]")
                            except Exception as e:
                                console.print(f"⚠️  Failed to export SARIF: {e}", style="yellow")

                        # Check if build should fail based on findings
                        if fail_on:
                            try:
                                console.print(f"\n🔍 Checking findings against severity threshold: {fail_on}")
                                findings = client.get_run_findings(response.run_id)
                                if should_fail_build(findings.sarif, fail_on):
                                    console.print("❌ [bold red]Build failed: Found blocking security issues[/bold red]")
                                    console.print(f"💡 View details: [bold cyan]fuzzforge finding {response.run_id}[/bold cyan]")
                                    raise typer.Exit(1)
                                else:
                                    console.print("✅ [bold green]No blocking security issues found[/bold green]")
                            except typer.Exit:
                                raise  # Re-raise Exit to preserve exit code
                            except Exception as e:
                                console.print(f"⚠️  Failed to check findings: {e}", style="yellow")

                        if not fail_on and not export_sarif:
                            console.print(f"💡 View findings: [bold cyan]fuzzforge findings {response.run_id}[/bold cyan]")

                except KeyboardInterrupt:
                    console.print("\n⏹️  Monitoring cancelled (execution continues in background)", style="yellow")
                except typer.Exit:
                    raise  # Re-raise Exit to preserve exit code
                except Exception as e:
                    handle_error(e, "waiting for completion")

    except typer.Exit:
        raise  # Re-raise Exit to preserve exit code
    except Exception as e:
        handle_error(e, "executing workflow")
    finally:
        # Stop worker if auto-stop is enabled and wait completed
        if should_auto_stop and worker_service and worker_mgr and wait_completed:
            try:
                console.print("\n🛑 Stopping worker (auto-stop enabled)...")
                if worker_mgr.stop_worker(worker_service):
                    console.print(f"✅ Worker stopped: {worker_service}")
            except Exception as e:
                console.print(
                    f"⚠️  Failed to stop worker: {e}",
                    style="yellow"
                )


@app.command("status")
def workflow_status(
    execution_id: Optional[str] = typer.Argument(None, help="Execution ID to check (defaults to most recent)")
):
    """
    📊 Check the status of a workflow execution
    """
    try:
        require_project()

        if execution_id:
            validate_run_id(execution_id)

        db = get_project_db()
        if not db:
            raise DatabaseError("get project database", Exception("No database found"))

        # Get execution ID
        if not execution_id:
            recent_runs = db.list_runs(limit=1)
            if not recent_runs:
                console.print("⚠️  No executions found in project database", style="yellow")
                raise typer.Exit(0)
            execution_id = recent_runs[0].run_id
            console.print(f"🔍 Using most recent execution: {execution_id}")
        else:
            validate_run_id(execution_id)

        # Get status from API
        with get_client() as client:
            status = client.get_run_status(execution_id)

        # Update local database
        try:
            db.update_run_status(
                execution_id,
                status.status,
                completed_at=status.updated_at if status.is_completed else None
            )
        except Exception as e:
            console.print(f"⚠️  Failed to update database: {e}", style="yellow")

        # Display status
        console.print(f"\n📊 [bold]Execution Status: {execution_id}[/bold]\n")

        status_table = Table(show_header=False, box=box.SIMPLE)
        status_table.add_column("Property", style="bold cyan")
        status_table.add_column("Value")

        status_table.add_row("Execution ID", execution_id)
        status_table.add_row("Workflow", status.workflow)
        status_table.add_row("Status", f"{status_emoji(status.status)} {status.status}")
        status_table.add_row("Created", status.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        status_table.add_row("Updated", status.updated_at.strftime("%Y-%m-%d %H:%M:%S"))

        if status.is_completed:
            duration = status.updated_at - status.created_at
            status_table.add_row("Duration", str(duration).split('.')[0])  # Remove microseconds

        console.print(
            Panel.fit(
                status_table,
                title="📊 Status Information",
                box=box.ROUNDED
            )
        )

        # Show next steps
        if status.is_running:
            console.print(f"\n💡 Monitor live: [bold cyan]fuzzforge monitor live {execution_id}[/bold cyan]")
        elif status.is_completed:
            console.print(f"💡 View findings: [bold cyan]fuzzforge finding {execution_id}[/bold cyan]")
        elif status.is_failed:
            console.print(f"💡 Check logs: [bold cyan]fuzzforge workflow logs {execution_id}[/bold cyan]")

    except Exception as e:
        handle_error(e, "getting execution status")


@app.command("history")
def workflow_history(
    workflow: Optional[str] = typer.Option(None, "--workflow", "-w", help="Filter by workflow name"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of executions to show")
):
    """
    📋 Show workflow execution history
    """
    try:
        require_project()

        if limit <= 0:
            raise ValidationError("limit", limit, "a positive integer")

        db = get_project_db()
        if not db:
            raise DatabaseError("get project database", Exception("No database found"))
        runs = db.list_runs(workflow=workflow, status=status, limit=limit)

        if not runs:
            console.print("⚠️  No executions found matching criteria", style="yellow")
            return

        table = Table(box=box.ROUNDED)
        table.add_column("Execution ID", style="bold cyan")
        table.add_column("Workflow", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Target", style="dim")
        table.add_column("Created", justify="center")
        table.add_column("Parameters", justify="center", style="dim")

        for run in runs:
            param_count = len(run.parameters) if run.parameters else 0
            param_str = f"{param_count} params" if param_count > 0 else "-"

            table.add_row(
                run.run_id[:12] + "..." if len(run.run_id) > MAX_RUN_ID_DISPLAY_LENGTH else run.run_id,
                run.workflow,
                f"{status_emoji(run.status)} {run.status}",
                Path(run.target_path).name,
                run.created_at.strftime("%m-%d %H:%M"),
                param_str
            )

        console.print(f"\n📋 [bold]Workflow Execution History ({len(runs)})[/bold]")
        if workflow:
            console.print(f"   Filtered by workflow: {workflow}")
        if status:
            console.print(f"   Filtered by status: {status}")
        console.print()
        console.print(table)

        console.print("\n💡 Use [bold cyan]fuzzforge workflow status <execution-id>[/bold cyan] for detailed status")

    except Exception as e:
        handle_error(e, "listing execution history")


@app.command("retry")
def retry_workflow(
    execution_id: Optional[str] = typer.Argument(None, help="Execution ID to retry (defaults to most recent)"),
    modify_params: bool = typer.Option(
        False, "--modify-params", "-m",
        help="Interactively modify parameters before retrying"
    )
):
    """
    🔄 Retry a workflow execution with the same or modified parameters
    """
    try:
        require_project()

        db = get_project_db()
        if not db:
            raise DatabaseError("get project database", Exception("No database found"))

        # Get execution ID if not provided
        if not execution_id:
            recent_runs = db.list_runs(limit=1)
            if not recent_runs:
                console.print("⚠️  No executions found to retry", style="yellow")
                raise typer.Exit(0)
            execution_id = recent_runs[0].run_id
            console.print(f"🔄 Retrying most recent execution: {execution_id}")
        else:
            validate_run_id(execution_id)

        # Get original execution
        original_run = db.get_run(execution_id)
        if not original_run:
            raise ValidationError("execution_id", execution_id, "an existing execution ID in the database")

        console.print(f"🔄 [bold]Retrying workflow:[/bold] {original_run.workflow}")
        console.print(f"   Original Execution ID: {execution_id}")
        console.print(f"   Target: {original_run.target_path}")

        parameters = original_run.parameters.copy()

        # Modify parameters if requested
        if modify_params and parameters:
            console.print("\n📝 [bold]Current parameters:[/bold]")
            for key, value in parameters.items():
                new_value = Prompt.ask(
                    f"{key}",
                    default=str(value),
                    console=console
                )
                if new_value != str(value):
                    # Try to maintain type
                    try:
                        if isinstance(value, bool):
                            parameters[key] = new_value.lower() in ("true", "yes", "1", "on")
                        elif isinstance(value, int):
                            parameters[key] = int(new_value)
                        elif isinstance(value, float):
                            parameters[key] = float(new_value)
                        elif isinstance(value, list):
                            parameters[key] = [item.strip() for item in new_value.split(",") if item.strip()]
                        else:
                            parameters[key] = new_value
                    except ValueError:
                        parameters[key] = new_value

        # Submit new execution
        with get_client() as client:
            submission = WorkflowSubmission(
                target_path=original_run.target_path,
                parameters=parameters
            )

            response = client.submit_workflow(original_run.workflow, submission)

            console.print("\n✅ Retry submitted successfully!", style="green")
            console.print(f"   New Execution ID: [bold cyan]{response.run_id}[/bold cyan]")
            console.print(f"   Status: {status_emoji(response.status)} {response.status}")

            # Save to database
            try:
                run_record = RunRecord(
                    run_id=response.run_id,
                    workflow=original_run.workflow,
                    status=response.status,
                    target_path=original_run.target_path,
                    parameters=parameters,
                    created_at=datetime.now(),
                    metadata={"retry_of": execution_id}
                )
                db.save_run(run_record)
            except Exception as e:
                console.print(f"⚠️  Failed to save execution to database: {e}", style="yellow")

            console.print(f"\n💡 Monitor progress: [bold cyan]fuzzforge monitor live {response.run_id}[/bold cyan]")

    except Exception as e:
        handle_error(e, "retrying workflow")


@app.callback()
def workflow_exec_callback():
    """
    🚀 Workflow execution management
    """