"""
Real-time monitoring and statistics commands.
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
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich import box

from ..config import get_project_config, FuzzForgeConfig
from ..database import ensure_project_db, CrashRecord
from fuzzforge_sdk import FuzzForgeClient

console = Console()
app = typer.Typer()


def get_client() -> FuzzForgeClient:
    """Get configured FuzzForge client"""
    config = get_project_config() or FuzzForgeConfig()
    return FuzzForgeClient(base_url=config.get_api_url(), timeout=config.get_timeout())


def format_duration(seconds: int) -> str:
    """Format duration in human readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def format_number(num: int) -> str:
    """Format large numbers with K, M suffixes"""
    if num >= 1000000:
        return f"{num / 1000000:.1f}M"
    elif num >= 1000:
        return f"{num / 1000:.1f}K"
    else:
        return str(num)


def create_stats_table(stats) -> Panel:
    """Create a rich table for fuzzing statistics"""
    # Create main stats table
    stats_table = Table(show_header=False, box=box.SIMPLE)
    stats_table.add_column("Metric", style="bold cyan")
    stats_table.add_column("Value", justify="right", style="bold white")

    stats_table.add_row("Total Executions", format_number(stats.executions))
    stats_table.add_row("Executions/sec", f"{stats.executions_per_sec:.1f}")
    stats_table.add_row("Total Crashes", format_number(stats.crashes))
    stats_table.add_row("Unique Crashes", format_number(stats.unique_crashes))

    if stats.coverage is not None and stats.coverage > 0:
        stats_table.add_row("Code Coverage", f"{stats.coverage} edges")

    stats_table.add_row("Corpus Size", format_number(stats.corpus_size))
    stats_table.add_row("Elapsed Time", format_duration(stats.elapsed_time))

    if stats.last_crash_time:
        time_since_crash = datetime.now() - stats.last_crash_time
        stats_table.add_row("Last Crash", f"{format_duration(int(time_since_crash.total_seconds()))} ago")

    return Panel.fit(
        stats_table,
        title=f"📊 Fuzzing Statistics - {stats.workflow}",
        subtitle=f"Run: {stats.run_id[:12]}...",
        box=box.ROUNDED
    )


@app.command("crashes")
def crash_reports(
    run_id: str = typer.Argument(..., help="Run ID to get crash reports for"),
    save: bool = typer.Option(
        True, "--save/--no-save",
        help="Save crashes to local database"
    ),
    limit: int = typer.Option(
        50, "--limit", "-l",
        help="Maximum number of crashes to show"
    )
):
    """
    🐛 Display crash reports for a fuzzing run
    """
    try:
        with get_client() as client:
            console.print(f"🐛 Fetching crash reports for run: {run_id}")
            crashes = client.get_crash_reports(run_id)

        if not crashes:
            console.print("✅ No crashes found!", style="green")
            return

        # Save to database if requested
        if save:
            db = ensure_project_db()
            for crash in crashes:
                crash_record = CrashRecord(
                    run_id=run_id,
                    crash_id=crash.crash_id,
                    signal=crash.signal,
                    stack_trace=crash.stack_trace,
                    input_file=crash.input_file,
                    severity=crash.severity,
                    timestamp=crash.timestamp
                )
                db.save_crash(crash_record)
            console.print("✅ Crashes saved to local database")

        # Display crashes
        crashes_to_show = crashes[:limit]

        # Summary
        severity_counts = {}
        signal_counts = {}
        for crash in crashes:
            severity_counts[crash.severity] = severity_counts.get(crash.severity, 0) + 1
            if crash.signal:
                signal_counts[crash.signal] = signal_counts.get(crash.signal, 0) + 1

        summary_table = Table(show_header=False, box=box.SIMPLE)
        summary_table.add_column("Metric", style="bold cyan")
        summary_table.add_column("Value", justify="right")

        summary_table.add_row("Total Crashes", str(len(crashes)))
        summary_table.add_row("Unique Signals", str(len(signal_counts)))

        for severity, count in sorted(severity_counts.items()):
            summary_table.add_row(f"{severity.title()} Severity", str(count))

        console.print(
            Panel.fit(
                summary_table,
                title="🐛 Crash Summary",
                box=box.ROUNDED
            )
        )

        # Detailed crash table
        if crashes_to_show:
            crashes_table = Table(box=box.ROUNDED)
            crashes_table.add_column("Crash ID", style="bold cyan")
            crashes_table.add_column("Signal", justify="center")
            crashes_table.add_column("Severity", justify="center")
            crashes_table.add_column("Timestamp", justify="center")
            crashes_table.add_column("Input File", style="dim")

            for crash in crashes_to_show:
                signal_emoji = {
                    "SIGSEGV": "💥",
                    "SIGABRT": "🛑",
                    "SIGFPE": "🧮",
                    "SIGILL": "⚠️"
                }.get(crash.signal or "", "🐛")

                severity_style = {
                    "high": "red",
                    "medium": "yellow",
                    "low": "green"
                }.get(crash.severity.lower(), "white")

                input_display = ""
                if crash.input_file:
                    input_display = crash.input_file.split("/")[-1]  # Show just filename

                crashes_table.add_row(
                    crash.crash_id[:12] + "..." if len(crash.crash_id) > 15 else crash.crash_id,
                    f"{signal_emoji} {crash.signal or 'Unknown'}",
                    f"[{severity_style}]{crash.severity}[/{severity_style}]",
                    crash.timestamp.strftime("%H:%M:%S"),
                    input_display
                )

            console.print("\n🐛 [bold]Crash Details[/bold]")
            if len(crashes) > limit:
                console.print(f"Showing first {limit} of {len(crashes)} crashes")
            console.print()
            console.print(crashes_table)

            console.print(f"\n💡 Use [bold cyan]fuzzforge finding {run_id}[/bold cyan] for detailed analysis")

    except Exception as e:
        console.print(f"❌ Failed to get crash reports: {e}", style="red")
        raise typer.Exit(1)


def _live_monitor(run_id: str, refresh: int, once: bool = False, style: str = "inline"):
    """Helper for live monitoring with inline real-time display or table display"""
    with get_client() as client:
        start_time = time.time()

        def render_inline_stats(run_status, stats):
            """Render inline stats display (non-dashboard)"""
            lines = []

            # Header line
            workflow_name = getattr(stats, 'workflow', 'unknown')
            status_emoji = "🔄" if not getattr(run_status, 'is_completed', False) else "✅"
            status_color = "yellow" if not getattr(run_status, 'is_completed', False) else "green"

            lines.append(f"\n[bold cyan]📊 Live Fuzzing Monitor[/bold cyan] - {workflow_name} (Run: {run_id[:12]}...)\n")

            # Stats lines with emojis
            lines.append(f"  [bold]⚡ Executions[/bold]     {format_number(stats.executions):>8}  [dim]({stats.executions_per_sec:,.1f}/sec)[/dim]")
            lines.append(f"  [bold]💥 Crashes[/bold]        {stats.crashes:>8}  [dim](unique: {stats.unique_crashes})[/dim]")
            lines.append(f"  [bold]📦 Corpus[/bold]         {stats.corpus_size:>8} inputs")

            if stats.coverage is not None and stats.coverage > 0:
                lines.append(f"  [bold]📈 Coverage[/bold]       {stats.coverage:>8} edges")

            lines.append(f"  [bold]⏱️  Elapsed[/bold]        {format_duration(stats.elapsed_time):>8}")

            # Last crash info
            if stats.last_crash_time:
                time_since = datetime.now() - stats.last_crash_time
                crash_ago = format_duration(int(time_since.total_seconds()))
                lines.append(f"  [bold red]🐛 Last Crash[/bold red]    {crash_ago:>8} ago")

            # Status line
            status_text = getattr(run_status, 'status', 'Unknown')
            current_time = datetime.now().strftime('%H:%M:%S')
            lines.append(f"\n[{status_color}]{status_emoji} Status: {status_text}[/{status_color}] | Last update: [dim]{current_time}[/dim] | Refresh: {refresh}s | [dim]Press Ctrl+C to stop[/dim]")

            return "\n".join(lines)

        # Fallback stats class
        class FallbackStats:
            def __init__(self, run_id):
                self.run_id = run_id
                self.workflow = "unknown"
                self.executions = 0
                self.executions_per_sec = 0.0
                self.crashes = 0
                self.unique_crashes = 0
                self.coverage = None
                self.corpus_size = 0
                self.elapsed_time = 0
                self.last_crash_time = None

        # Initial fetch
        try:
            run_status = client.get_run_status(run_id)
            stats = client.get_fuzzing_stats(run_id)
        except Exception:
            stats = FallbackStats(run_id)
            run_status = type("RS", (), {"status":"Unknown","is_completed":False,"is_failed":False})()

        # Handle --once mode: show stats once and exit
        if once:
            if style == "table":
                console.print(create_stats_table(stats))
            else:
                console.print(render_inline_stats(run_status, stats))
            return

        # Live monitoring mode
        with Live(auto_refresh=False, console=console) as live:
            # Render based on style
            if style == "table":
                live.update(create_stats_table(stats), refresh=True)
            else:
                live.update(render_inline_stats(run_status, stats), refresh=True)

            # Polling loop
            consecutive_errors = 0
            max_errors = 5

            while True:
                try:
                    # Poll for updates
                    try:
                        run_status = client.get_run_status(run_id)
                        consecutive_errors = 0
                    except Exception as e:
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            console.print(f"\n❌ Too many errors getting run status: {e}", style="red")
                            break
                        time.sleep(refresh)
                        continue

                    # Try to get fuzzing stats
                    try:
                        stats = client.get_fuzzing_stats(run_id)
                    except Exception:
                        stats = FallbackStats(run_id)

                    # Update display based on style
                    if style == "table":
                        live.update(create_stats_table(stats), refresh=True)
                    else:
                        live.update(render_inline_stats(run_status, stats), refresh=True)

                    # Check if completed
                    if getattr(run_status, 'is_completed', False) or getattr(run_status, 'is_failed', False):
                        break

                    # Wait before next poll
                    time.sleep(refresh)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    console.print(f"\n⚠️ Monitoring error: {e}", style="yellow")
                    time.sleep(refresh)

            # Final status
            final_status = getattr(run_status, 'status', 'Unknown')
            total_time = format_duration(int(time.time() - start_time))

            if getattr(run_status, 'is_completed', False):
                console.print(f"\n✅ [bold green]Run completed successfully[/bold green] | Total runtime: {total_time}")
            else:
                console.print(f"\n⚠️ [bold yellow]Run ended[/bold yellow] | Status: {final_status} | Total runtime: {total_time}")


@app.command("live")
def live_monitor(
    run_id: str = typer.Argument(..., help="Run ID to monitor live"),
    refresh: int = typer.Option(
        2, "--refresh", "-r",
        help="Refresh interval in seconds"
    ),
    once: bool = typer.Option(
        False, "--once",
        help="Show stats once and exit"
    ),
    style: str = typer.Option(
        "inline", "--style",
        help="Display style: 'inline' (default) or 'table'"
    )
):
    """
    📺 Real-time monitoring with live statistics updates

    Display styles:
    - inline: Visual inline display with emojis (default)
    - table: Clean table-based display

    Use --once to show stats once without continuous monitoring (useful for scripts)
    """
    try:
        # Validate style
        if style not in ["inline", "table"]:
            console.print(f"❌ Invalid style: {style}. Must be 'inline' or 'table'", style="red")
            raise typer.Exit(1)

        _live_monitor(run_id, refresh, once, style)
    except KeyboardInterrupt:
        console.print("\n\n📊 Monitoring stopped by user.", style="yellow")
    except Exception as e:
        console.print(f"\n❌ Failed to start monitoring: {e}", style="red")
        raise typer.Exit(1)


def create_progress_bar(percentage: float, color: str = "green") -> str:
    """Create a simple text progress bar"""
    width = 20
    filled = int((percentage / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {percentage:.1f}%"


@app.callback(invoke_without_command=True)
def monitor_callback(ctx: typer.Context):
    """
    📊 Real-time monitoring and statistics
    """
    # Check if a subcommand is being invoked
    if ctx.invoked_subcommand is not None:
        # Let the subcommand handle it
        return

    # Show help message for default command
    from rich.console import Console
    console = Console()
    console.print("📊 [bold cyan]Monitor Command[/bold cyan]")
    console.print("\nAvailable subcommands:")
    console.print("  • [cyan]ff monitor live <run-id>[/cyan] - Monitor with live updates (supports --once, --style)")
    console.print("  • [cyan]ff monitor crashes <run-id>[/cyan] - Show crash reports")
