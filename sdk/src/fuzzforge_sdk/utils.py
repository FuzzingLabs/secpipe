"""
Utility functions for the FuzzForge SDK.

Provides helper functions for path validation, SARIF processing,
volume mount creation, and other common operations.
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


import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from .models import WorkflowSubmission
from .exceptions import ValidationError


def validate_absolute_path(path: Union[str, Path]) -> Path:
    """
    Validate that a path is absolute and exists.

    Args:
        path: Path to validate

    Returns:
        Validated Path object

    Raises:
        ValidationError: If path is not absolute or doesn't exist
    """
    path_obj = Path(path)

    if not path_obj.is_absolute():
        raise ValidationError(f"Path must be absolute: {path}")

    if not path_obj.exists():
        raise ValidationError(f"Path does not exist: {path}")

    return path_obj


def create_workflow_submission(
    parameters: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None
) -> WorkflowSubmission:
    """
    Create a workflow submission.

    Note: This function is deprecated. Use client.submit_workflow_with_upload() instead
    which handles file uploads automatically.

    Args:
        parameters: Workflow-specific parameters
        timeout: Execution timeout in seconds

    Returns:
        WorkflowSubmission object

    Raises:
        ValidationError: If parameters are invalid
    """
    # Validate timeout
    if timeout is not None:
        if timeout < 1 or timeout > 604800:  # Max 7 days
            raise ValidationError(f"Timeout must be between 1 and 604800 seconds: {timeout}")

    return WorkflowSubmission(
        parameters=parameters or {},
        timeout=timeout
    )


def extract_sarif_results(sarif_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract results from SARIF format findings.

    Args:
        sarif_data: SARIF formatted data

    Returns:
        List of result objects from SARIF

    Raises:
        ValidationError: If SARIF data is malformed
    """
    if not isinstance(sarif_data, dict):
        raise ValidationError("SARIF data must be a dictionary")

    runs = sarif_data.get("runs", [])
    if not isinstance(runs, list):
        raise ValidationError("SARIF runs must be a list")

    results = []
    for run in runs:
        if not isinstance(run, dict):
            continue

        run_results = run.get("results", [])
        if isinstance(run_results, list):
            results.extend(run_results)

    return results


def count_sarif_severity_levels(sarif_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Count findings by severity level in SARIF data.

    Args:
        sarif_data: SARIF formatted data

    Returns:
        Dictionary mapping severity levels to counts
    """
    results = extract_sarif_results(sarif_data)
    severity_counts = {"error": 0, "warning": 0, "note": 0, "info": 0}

    for result in results:
        level = result.get("level", "warning")
        if level in severity_counts:
            severity_counts[level] += 1
        else:
            # Default unknown levels to warning
            severity_counts["warning"] += 1

    return severity_counts


def format_sarif_summary(sarif_data: Dict[str, Any]) -> str:
    """
    Create a human-readable summary of SARIF findings.

    Args:
        sarif_data: SARIF formatted data

    Returns:
        Formatted summary string
    """
    severity_counts = count_sarif_severity_levels(sarif_data)
    total_findings = sum(severity_counts.values())

    if total_findings == 0:
        return "No findings detected."

    summary_parts = [f"Total findings: {total_findings}"]

    for level, count in severity_counts.items():
        if count > 0:
            summary_parts.append(f"{level.title()}: {count}")

    return " | ".join(summary_parts)


def save_sarif_to_file(sarif_data: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """
    Save SARIF data to a JSON file.

    Args:
        sarif_data: SARIF formatted data
        file_path: Path to save the file

    Raises:
        ValidationError: If file cannot be written
    """
    try:
        path_obj = Path(file_path)
        # Create parent directories if they don't exist
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(path_obj, 'w', encoding='utf-8') as f:
            json.dump(sarif_data, f, indent=2, ensure_ascii=False)

    except (OSError, json.JSONEncodeError) as e:
        raise ValidationError(f"Failed to save SARIF file: {e}")


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}m {secs}s"
    else:
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}h {minutes}m {secs}s"


def format_execution_rate(executions_per_sec: float) -> str:
    """
    Format execution rate for display.

    Args:
        executions_per_sec: Executions per second

    Returns:
        Formatted rate string
    """
    if executions_per_sec < 1:
        return f"{executions_per_sec:.2f} exec/s"
    elif executions_per_sec < 1000:
        return f"{executions_per_sec:.1f} exec/s"
    else:
        return f"{executions_per_sec/1000:.1f}k exec/s"


def format_memory_size(size_bytes: int) -> str:
    """
    Format memory size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def get_project_files(
    project_path: Union[str, Path],
    extensions: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None
) -> List[Path]:
    """
    Get list of files in a project directory.

    Args:
        project_path: Path to project directory
        extensions: List of file extensions to include (e.g., ['.py', '.js'])
        exclude_dirs: List of directory names to exclude (e.g., ['.git', 'node_modules'])

    Returns:
        List of file paths

    Raises:
        ValidationError: If project path is invalid
    """
    project_path_obj = validate_absolute_path(project_path)

    if not project_path_obj.is_dir():
        raise ValidationError(f"Project path must be a directory: {project_path}")

    exclude_dirs = exclude_dirs or ['.git', '__pycache__', 'node_modules', '.pytest_cache']
    extensions = extensions or []

    files = []

    for root, dirs, filenames in os.walk(project_path_obj):
        # Remove excluded directories from search
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        root_path = Path(root)

        for filename in filenames:
            file_path = root_path / filename

            # Filter by extensions if specified
            if extensions and not any(filename.endswith(ext) for ext in extensions):
                continue

            files.append(file_path)

    return sorted(files)


def estimate_analysis_time(
    project_path: Union[str, Path],
    workflow_type: str = "static"
) -> int:
    """
    Estimate analysis time based on project size and workflow type.

    Args:
        project_path: Path to project directory
        workflow_type: Type of workflow ("static", "dynamic", "fuzzing")

    Returns:
        Estimated time in seconds

    Raises:
        ValidationError: If project path is invalid
    """
    files = get_project_files(project_path)
    total_size = sum(f.stat().st_size for f in files if f.exists())

    # Base estimates (very rough)
    if workflow_type == "static":
        # ~1MB per second for static analysis
        base_time = max(30, total_size // (1024 * 1024))
    elif workflow_type == "dynamic":
        # Dynamic analysis is slower
        base_time = max(60, total_size // (512 * 1024))
    elif workflow_type == "fuzzing":
        # Fuzzing can run for hours/days
        base_time = 3600  # Default to 1 hour
    else:
        # Unknown workflow type
        base_time = max(60, total_size // (1024 * 1024))

    # Factor in number of files
    file_factor = max(1, len(files) // 100)

    return base_time * file_factor