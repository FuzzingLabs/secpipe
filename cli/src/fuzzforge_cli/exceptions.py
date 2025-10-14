"""
Enhanced exception handling and error utilities for FuzzForge CLI with rich context display.
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
import functools
from typing import Any, Callable, Optional, Union, List
from pathlib import Path

import typer
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

# Import SDK exceptions for rich handling
from fuzzforge_sdk.exceptions import (
    FuzzForgeError as SDKFuzzForgeError
)

console = Console()


class FuzzForgeError(Exception):
    """Base exception for FuzzForge CLI errors (legacy CLI-specific errors)"""

    def __init__(self, message: str, hint: Optional[str] = None, exit_code: int = 1):
        self.message = message
        self.hint = hint
        self.exit_code = exit_code
        super().__init__(message)


class ProjectNotFoundError(FuzzForgeError):
    """Raised when no FuzzForge project is found in current directory"""

    def __init__(self):
        super().__init__(
            "No FuzzForge project found in current directory",
            "Run 'ff init' to initialize a new project"
        )


class APIConnectionError(FuzzForgeError):
    """Legacy API connection error for backward compatibility"""

    def __init__(self, url: str, original_error: Exception):
        self.url = url
        self.original_error = original_error

        if isinstance(original_error, httpx.ConnectTimeout):
            message = f"Connection timeout to FuzzForge API at {url}"
            hint = "Check if the API server is running and the URL is correct"
        elif isinstance(original_error, httpx.ConnectError):
            message = f"Failed to connect to FuzzForge API at {url}"
            hint = "Verify the API URL is correct and the server is accessible"
        elif isinstance(original_error, httpx.TimeoutException):
            message = f"Request timeout to FuzzForge API at {url}"
            hint = "The API server may be overloaded. Try again later"
        else:
            message = f"API connection error: {str(original_error)}"
            hint = "Check your network connection and API configuration"

        super().__init__(message, hint)


class DatabaseError(FuzzForgeError):
    """Raised when database operations fail"""

    def __init__(self, operation: str, original_error: Exception):
        self.operation = operation
        self.original_error = original_error

        message = f"Database error during {operation}: {str(original_error)}"
        hint = "The database may be corrupted. Try 'ff init --force' to reset"

        super().__init__(message, hint)


class ValidationError(FuzzForgeError):
    """Legacy validation error for CLI-specific validation"""

    def __init__(self, field: str, value: Any, expected: str):
        self.field = field
        self.value = value
        self.expected = expected

        message = f"Invalid {field}: {value}"
        hint = f"Expected {expected}"

        super().__init__(message, hint)


class FileOperationError(FuzzForgeError):
    """Raised when file operations fail"""

    def __init__(self, operation: str, path: Union[str, Path], original_error: Exception):
        self.operation = operation
        self.path = Path(path)
        self.original_error = original_error

        if isinstance(original_error, FileNotFoundError):
            message = f"File not found: {path}"
            hint = "Check the path exists and you have permission to access it"
        elif isinstance(original_error, PermissionError):
            message = f"Permission denied: {path}"
            hint = "Check file permissions or run with appropriate privileges"
        else:
            message = f"File operation failed ({operation}): {str(original_error)}"
            hint = "Check the file path and permissions"

        super().__init__(message, hint)


def display_container_logs(diagnostics, title: str = "Container Logs"):
    """Display container logs in a rich format."""
    if not diagnostics or not diagnostics.logs:
        return

    # Show last 20 lines of logs
    recent_logs = diagnostics.logs[-20:] if len(diagnostics.logs) > 20 else diagnostics.logs

    log_content = []
    for log_entry in recent_logs:
        timestamp = log_entry.timestamp.strftime("%H:%M:%S")
        level_color = {
            'ERROR': 'red',
            'WARNING': 'yellow',
            'INFO': 'blue',
            'DEBUG': 'dim white'
        }.get(log_entry.level, 'white')

        log_line = f"[dim]{timestamp}[/dim] [{level_color}]{log_entry.level}[/{level_color}] {log_entry.message}"
        log_content.append(log_line)

    if log_content:
        logs_panel = Panel(
            "\n".join(log_content),
            title=title,
            title_align="left",
            border_style="dim",
            expand=False
        )
        console.print(logs_panel)


def display_container_diagnostics(diagnostics):
    """Display comprehensive container diagnostics."""
    if not diagnostics:
        return

    # Container Status Table
    status_table = Table(title="Container Status", show_header=False, box=None)
    status_table.add_column("Property", style="bold")
    status_table.add_column("Value")

    status_color = {
        'running': 'green',
        'exited': 'red',
        'failed': 'red',
        'created': 'yellow',
        'unknown': 'dim'
    }.get(diagnostics.status.lower(), 'white')

    status_table.add_row("Status", f"[{status_color}]{diagnostics.status}[/{status_color}]")

    if diagnostics.exit_code is not None:
        exit_color = 'green' if diagnostics.exit_code == 0 else 'red'
        status_table.add_row("Exit Code", f"[{exit_color}]{diagnostics.exit_code}[/{exit_color}]")

    if diagnostics.error:
        status_table.add_row("Error", f"[red]{diagnostics.error}[/red]")

    # Resource Usage
    if diagnostics.resource_usage:
        memory_limit = diagnostics.resource_usage.get('memory_limit', 0)
        if memory_limit > 0:
            memory_mb = memory_limit // (1024 * 1024)
            status_table.add_row("Memory Limit", f"{memory_mb} MB")

    console.print(status_table)

    # Volume Mounts
    if diagnostics.volume_mounts:
        console.print("\n[bold]Volume Mounts:[/bold]")
        for mount in diagnostics.volume_mounts:
            mount_info = f"  {mount['source']} → {mount['destination']} ([dim]{mount['mode']}[/dim])"
            console.print(mount_info)


def display_error_patterns(error_patterns):
    """Display detected error patterns."""
    if not error_patterns:
        return

    console.print("\n[bold red]🔍 Detected Issues:[/bold red]")

    for error_type, messages in error_patterns.items():
        # Format error type name
        formatted_type = error_type.replace('_', ' ').title()
        console.print(f"\n[bold yellow]• {formatted_type}:[/bold yellow]")

        for message in messages[:3]:  # Show first 3 messages
            console.print(f"  [dim]▸[/dim] {message}")

        if len(messages) > 3:
            console.print(f"  [dim]▸ ... and {len(messages) - 3} more similar messages[/dim]")


def display_suggestions(suggestions: List[str]):
    """Display actionable suggestions."""
    if not suggestions:
        return

    console.print("\n[bold green]💡 Suggested Fixes:[/bold green]")

    for i, suggestion in enumerate(suggestions[:6], 1):  # Show max 6 suggestions
        console.print(f"  [bold green]{i}.[/bold green] {suggestion}")


def handle_error(error: Exception, context: str = "") -> None:
    """
    Display comprehensive error messages with rich context and exit appropriately.

    Args:
        error: The exception that occurred
        context: Additional context about where the error occurred
    """
    # Handle SDK errors with rich context
    if isinstance(error, SDKFuzzForgeError):
        console.print()  # Add some spacing

        # Main error message
        error_title = f"❌ {error.__class__.__name__}"
        if context:
            error_title += f" during {context}"

        console.print(Panel(
            error.get_summary(),
            title=error_title,
            title_align="left",
            border_style="red",
            expand=False
        ))

        # Show detailed context if available
        if hasattr(error, 'context') and error.context:
            ctx = error.context

            # Error patterns
            if ctx.error_patterns:
                display_error_patterns(ctx.error_patterns)

            # API context
            if ctx.url:
                console.print(f"\n[dim]Request URL: {ctx.url}[/dim]")

            if ctx.response_data and isinstance(ctx.response_data, dict) and 'raw' not in ctx.response_data:
                console.print(f"[dim]API Response: {ctx.response_data}[/dim]")

            # Suggestions
            if ctx.suggested_fixes:
                display_suggestions(ctx.suggested_fixes)

        console.print()  # Add spacing before exit
        raise typer.Exit(1)

    # Handle legacy CLI errors
    elif isinstance(error, FuzzForgeError):
        error_text = Text()
        error_text.append("❌ ", style="red")
        error_text.append(error.message, style="red")

        if context:
            error_text.append(f" ({context})", style="dim red")

        console.print(error_text)

        if error.hint:
            hint_text = Text()
            hint_text.append("💡 ", style="yellow")
            hint_text.append(error.hint, style="yellow")
            console.print(hint_text)

        raise typer.Exit(error.exit_code)

    elif isinstance(error, KeyboardInterrupt):
        console.print("\n⏹️  Operation cancelled by user", style="yellow")
        raise typer.Exit(130)  # Standard exit code for SIGINT

    else:
        # Unexpected errors - show minimal info to user, log details
        console.print()

        error_panel = Panel(
            f"An unexpected error occurred: {str(error)}",
            title="❌ Unexpected Error",
            title_align="left",
            border_style="red",
            expand=False
        )

        if context:
            error_panel.title += f" during {context}"

        console.print(error_panel)

        # Show error details for debugging
        console.print(f"\n[dim yellow]Error type: {type(error).__name__}[/dim yellow]")
        console.print("[dim yellow]Please report this issue if it persists[/dim yellow]")
        console.print()

        raise typer.Exit(1)


def retry_on_network_error(max_retries: int = 3, delay: float = 1.0, backoff_multiplier: float = 2.0):
    """
    Decorator to retry network operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                    last_exception = e

                    if attempt < max_retries:
                        console.print(
                            f"🔄 Network error, retrying in {current_delay:.1f}s... "
                            f"(attempt {attempt + 1}/{max_retries})",
                            style="yellow"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    else:
                        # Convert to our custom error type
                        api_url = getattr(args[0], 'base_url', 'unknown') if args else 'unknown'
                        raise APIConnectionError(str(api_url), e)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def validate_path(path: Union[str, Path], must_exist: bool = True, must_be_file: bool = False,
                 must_be_dir: bool = False) -> Path:
    """
    Validate file/directory paths with user-friendly error messages.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist
        must_be_file: Whether the path must be a file
        must_be_dir: Whether the path must be a directory

    Returns:
        Validated Path object

    Raises:
        ValidationError: If validation fails
    """
    path_obj = Path(path)

    if must_exist and not path_obj.exists():
        raise ValidationError("path", str(path), "an existing path")

    if must_be_file and path_obj.exists() and not path_obj.is_file():
        raise ValidationError("path", str(path), "a file")

    if must_be_dir and path_obj.exists() and not path_obj.is_dir():
        raise ValidationError("path", str(path), "a directory")

    return path_obj


def validate_run_id(run_id: str) -> str:
    """
    Validate run ID format.

    Args:
        run_id: Run ID to validate

    Returns:
        Validated run ID

    Raises:
        ValidationError: If run ID format is invalid
    """
    if not run_id or len(run_id) < 8:
        raise ValidationError("run_id", run_id, "at least 8 characters")

    # Allow alphanumeric characters, hyphens, and underscores
    if not run_id.replace('-', '').replace('_', '').isalnum():
        raise ValidationError("run_id", run_id, "alphanumeric characters, hyphens, and underscores only")

    return run_id


def safe_json_load(file_path: Union[str, Path]) -> dict:
    """
    Safely load JSON file with proper error handling.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data

    Raises:
        FileOperationError: If file operation fails
        ValidationError: If JSON is invalid
    """
    path_obj = Path(file_path)

    try:
        with open(path_obj, 'r', encoding='utf-8') as f:
            import json
            return json.load(f)
    except FileNotFoundError as e:
        raise FileOperationError("read", path_obj, e)
    except PermissionError as e:
        raise FileOperationError("read", path_obj, e)
    except json.JSONDecodeError as e:
        raise ValidationError("JSON file", str(path_obj), f"valid JSON format (error: {e})")
    except Exception as e:
        raise FileOperationError("read", path_obj, e)


def require_project() -> Path:
    """
    Ensure we're in a FuzzForge project directory.

    Returns:
        Path to project root

    Raises:
        ProjectNotFoundError: If not in a project directory
    """
    current = Path.cwd()

    # Look for .fuzzforge directory in current or parent directories
    for path in [current] + list(current.parents):
        fuzzforge_dir = path / ".fuzzforge"
        if fuzzforge_dir.is_dir():
            return path

    raise ProjectNotFoundError()