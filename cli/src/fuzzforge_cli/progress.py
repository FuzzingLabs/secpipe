"""
Enhanced progress indicators and loading animations for FuzzForge CLI.

Provides rich progress bars, spinners, and status displays for all long-running operations.
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


import time
from contextlib import contextmanager
from typing import Optional, Any, Dict, List
from datetime import datetime

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn,
    TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
)
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


class ProgressManager:
    """Enhanced progress manager with multiple progress types."""

    def __init__(self):
        self.progress = None
        self.live = None

    def create_progress(self, show_speed: bool = False, show_eta: bool = False) -> Progress:
        """Create a rich progress instance with customizable columns."""
        columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
        ]

        if show_speed:
            columns.append(TextColumn("[cyan]{task.fields[speed]}/s"))

        columns.extend([
            TimeElapsedColumn(),
        ])

        if show_eta:
            columns.append(TimeRemainingColumn())

        return Progress(*columns, console=console)

    @contextmanager
    def workflow_submission(self, workflow_name: str, target_path: str):
        """Progress context for workflow submission."""
        with self.create_progress() as progress:
            task = progress.add_task(
                f"🚀 Submitting workflow: [yellow]{workflow_name}[/yellow]",
                total=4
            )

            # Step 1: Validation
            progress.update(task, description="🔍 Validating parameters...", advance=1)
            yield progress, task

            # Step 2: API Connection
            progress.update(task, description="🌐 Connecting to API...", advance=1)
            time.sleep(0.5)  # Brief pause for visual feedback

            # Step 3: Submission
            progress.update(task, description="📤 Submitting workflow...", advance=1)
            time.sleep(0.3)

            # Step 4: Complete
            progress.update(task, description="✅ Workflow submitted successfully!", advance=1)

    @contextmanager
    def data_export(self, format_type: str, record_count: int):
        """Progress context for data export operations."""
        with self.create_progress(show_eta=True) as progress:
            task = progress.add_task(
                f"📊 Exporting {record_count} records as [yellow]{format_type.upper()}[/yellow]",
                total=record_count
            )
            yield progress, task

    @contextmanager
    def file_operations(self, operation: str, file_count: int):
        """Progress context for file operations."""
        with self.create_progress(show_eta=True) as progress:
            task = progress.add_task(
                f"📁 {operation} {file_count} files...",
                total=file_count
            )
            yield progress, task

    @contextmanager
    def api_requests(self, operation: str, request_count: Optional[int] = None):
        """Progress context for API requests."""
        if request_count:
            with self.create_progress() as progress:
                task = progress.add_task(
                    f"🌐 {operation}...",
                    total=request_count
                )
                yield progress, task
        else:
            # Indeterminate progress for unknown request count
            with self.create_progress() as progress:
                task = progress.add_task(
                    f"🌐 {operation}...",
                    total=None
                )
                yield progress, task

    def create_live_stats_display(self) -> Dict[str, Any]:
        """Create a live statistics display layout."""
        return {
            "layout": None,
            "stats_table": None,
            "progress_bars": None
        }


@contextmanager
def spinner(text: str, success_text: Optional[str] = None):
    """Simple spinner context manager for quick operations."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(text, total=None)
        try:
            yield progress
            if success_text:
                progress.update(task, description=f"✅ {success_text}")
                time.sleep(0.5)  # Brief pause to show success
        except Exception as e:
            progress.update(task, description=f"❌ Failed: {str(e)}")
            time.sleep(0.5)
            raise


@contextmanager
def step_progress(steps: List[str], title: str = "Processing"):
    """Multi-step progress with predefined steps."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        console=console
    ) as progress:
        task = progress.add_task(f"🔄 {title}", total=len(steps))

        class StepProgressController:
            def __init__(self, progress_instance, task_id):
                self.progress = progress_instance
                self.task = task_id
                self.current_step = 0

            def next_step(self):
                if self.current_step < len(steps):
                    step_text = steps[self.current_step]
                    self.progress.update(
                        self.task,
                        description=f"🔄 {step_text}",
                        advance=1
                    )
                    self.current_step += 1

            def complete(self, success_text: str = "Completed"):
                self.progress.update(
                    self.task,
                    description=f"✅ {success_text}",
                    completed=len(steps)
                )

        yield StepProgressController(progress, task)


def create_workflow_monitoring_display(run_id: str, workflow_name: str) -> Table:
    """Create a monitoring display for workflow execution."""
    table = Table(show_header=False, box=box.ROUNDED)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", justify="right")

    table.add_row("Run ID", f"[dim]{run_id[:12]}...[/dim]")
    table.add_row("Workflow", f"[yellow]{workflow_name}[/yellow]")
    table.add_row("Status", "[orange]Running[/orange]")
    table.add_row("Started", datetime.now().strftime("%H:%M:%S"))

    return Panel.fit(
        table,
        title="🔄 Workflow Monitoring",
        border_style="blue"
    )


def create_fuzzing_progress_display(stats: Dict[str, Any]) -> Panel:
    """Create a rich display for fuzzing progress."""
    # Main stats table
    stats_table = Table(show_header=False, box=box.SIMPLE)
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", justify="right", style="bold white")

    stats_table.add_row("Executions", f"{stats.get('executions', 0):,}")
    stats_table.add_row("Exec/sec", f"{stats.get('executions_per_sec', 0):.1f}")
    stats_table.add_row("Crashes", f"[red]{stats.get('crashes', 0):,}[/red]")
    stats_table.add_row("Coverage", f"{stats.get('coverage', 0):.1f}%")

    # Progress bars
    progress_table = Table(show_header=False, box=box.SIMPLE)
    progress_table.add_column("Metric", style="bold")
    progress_table.add_column("Progress", min_width=25)

    # Execution rate progress (as percentage of target rate)
    exec_rate = stats.get('executions_per_sec', 0)
    target_rate = 1000  # Target 1000 exec/sec
    exec_progress = min(100, (exec_rate / target_rate) * 100)
    progress_table.add_row(
        "Exec Rate",
        create_progress_bar(exec_progress, color="green")
    )

    # Coverage progress
    coverage = stats.get('coverage', 0)
    progress_table.add_row(
        "Coverage",
        create_progress_bar(coverage, color="blue")
    )

    # Combine tables
    combined = Table(show_header=False, box=None)
    combined.add_column("Stats", ratio=1)
    combined.add_column("Progress", ratio=1)
    combined.add_row(stats_table, progress_table)

    return Panel(
        combined,
        title="🎯 Fuzzing Progress",
        border_style="green"
    )


def create_progress_bar(percentage: float, color: str = "green", width: int = 20) -> Text:
    """Create a visual progress bar using Rich Text."""
    filled = int((percentage / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    text = Text(bar, style=color)
    text.append(f" {percentage:.1f}%", style="dim")
    return text


def create_loading_animation(text: str) -> Live:
    """Create a loading animation with rotating spinner."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    frame_index = 0

    def get_spinner_frame():
        nonlocal frame_index
        frame = frames[frame_index]
        frame_index = (frame_index + 1) % len(frames)
        return frame

    panel = Panel(
        f"{get_spinner_frame()} [bold blue]{text}[/bold blue]",
        box=box.ROUNDED,
        border_style="cyan"
    )

    return Live(panel, auto_refresh=True, refresh_per_second=10)


class WorkflowProgressTracker:
    """Advanced progress tracker for workflow execution."""

    def __init__(self, workflow_name: str, run_id: str):
        self.workflow_name = workflow_name
        self.run_id = run_id
        self.start_time = datetime.now()
        self.phases = []
        self.current_phase = None

    def add_phase(self, name: str, description: str, estimated_duration: Optional[int] = None):
        """Add a phase to the workflow progress."""
        self.phases.append({
            "name": name,
            "description": description,
            "estimated_duration": estimated_duration,
            "start_time": None,
            "end_time": None,
            "status": "pending"
        })

    def start_phase(self, phase_name: str):
        """Start a specific phase."""
        for phase in self.phases:
            if phase["name"] == phase_name:
                phase["start_time"] = datetime.now()
                phase["status"] = "running"
                self.current_phase = phase_name
                break

    def complete_phase(self, phase_name: str, success: bool = True):
        """Complete a specific phase."""
        for phase in self.phases:
            if phase["name"] == phase_name:
                phase["end_time"] = datetime.now()
                phase["status"] = "completed" if success else "failed"
                self.current_phase = None
                break

    def get_progress_display(self) -> Panel:
        """Get the current progress display."""
        # Create progress table
        table = Table(show_header=True, box=box.ROUNDED)
        table.add_column("Phase", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Duration")

        for phase in self.phases:
            status_emoji = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌"
            }

            status_text = f"{status_emoji.get(phase['status'], '❓')} {phase['status'].title()}"

            # Calculate duration
            if phase["start_time"]:
                end_time = phase["end_time"] or datetime.now()
                duration = end_time - phase["start_time"]
                duration_text = f"{duration.seconds}s"
            else:
                duration_text = "-"

            table.add_row(
                phase["description"],
                status_text,
                duration_text
            )

        total_duration = datetime.now() - self.start_time
        title = f"🔄 {self.workflow_name} Progress (Run: {self.run_id[:8]}..., {total_duration.seconds}s)"

        return Panel(
            table,
            title=title,
            border_style="blue"
        )


# Global progress manager instance
progress_manager = ProgressManager()