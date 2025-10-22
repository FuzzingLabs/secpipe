"""
Shell auto-completion support for FuzzForge CLI.

Provides intelligent tab completion for commands, workflows, run IDs, and parameters.
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
from typing import List
from pathlib import Path

from .config import get_project_config, FuzzForgeConfig
from .database import get_project_db
from fuzzforge_sdk import FuzzForgeClient


def complete_workflow_names(incomplete: str) -> List[str]:
    """Auto-complete workflow names from the API."""
    try:
        config = get_project_config() or FuzzForgeConfig()
        with FuzzForgeClient(base_url=config.get_api_url(), timeout=5.0) as client:
            workflows = client.list_workflows()
            workflow_names = [w.name for w in workflows]
            return [name for name in workflow_names if name.startswith(incomplete)]
    except Exception:
        # Fallback to common workflow names if API is unavailable
        common_workflows = [
            "security_assessment",
            "language_fuzzing",
            "infrastructure_scan",
            "static_analysis_scan",
            "penetration_testing_scan",
            "secret_detection_scan"
        ]
        return [name for name in common_workflows if name.startswith(incomplete)]


def complete_run_ids(incomplete: str) -> List[str]:
    """Auto-complete run IDs from local database."""
    try:
        db = get_project_db()
        if db:
            runs = db.get_recent_runs(limit=50)  # Get recent runs for completion
            run_ids = [run.run_id for run in runs]
            return [run_id for run_id in run_ids if run_id.startswith(incomplete)]
    except Exception:
        pass
    return []


def complete_target_paths(incomplete: str) -> List[str]:
    """Auto-complete file/directory paths."""
    try:
        # Convert incomplete path to Path object
        path = Path(incomplete) if incomplete else Path.cwd()

        if path.is_dir():
            # Complete directory contents
            try:
                entries = []
                for entry in path.iterdir():
                    entry_str = str(entry)
                    if entry.is_dir():
                        entry_str += "/"
                    entries.append(entry_str)
                return entries
            except PermissionError:
                return []
        else:
            # Complete parent directory contents that match the incomplete name
            parent = path.parent
            name = path.name
            try:
                entries = []
                for entry in parent.iterdir():
                    if entry.name.startswith(name):
                        entry_str = str(entry)
                        if entry.is_dir():
                            entry_str += "/"
                        entries.append(entry_str)
                return entries
            except (PermissionError, FileNotFoundError):
                return []
    except Exception:
        return []


def complete_export_formats(incomplete: str) -> List[str]:
    """Auto-complete export formats."""
    formats = ["json", "csv", "html", "sarif"]
    return [fmt for fmt in formats if fmt.startswith(incomplete)]


def complete_severity_levels(incomplete: str) -> List[str]:
    """Auto-complete severity levels."""
    severities = ["critical", "high", "medium", "low", "info"]
    return [sev for sev in severities if sev.startswith(incomplete)]


def complete_workflow_tags(incomplete: str) -> List[str]:
    """Auto-complete workflow tags."""
    try:
        config = get_project_config() or FuzzForgeConfig()
        with FuzzForgeClient(base_url=config.get_api_url(), timeout=5.0) as client:
            workflows = client.list_workflows()
            all_tags = set()
            for w in workflows:
                if w.tags:
                    all_tags.update(w.tags)
            return [tag for tag in sorted(all_tags) if tag.startswith(incomplete)]
    except Exception:
        # Fallback tags
        common_tags = [
            "security", "fuzzing", "static-analysis", "infrastructure",
            "secrets", "containers", "vulnerabilities", "pentest"
        ]
        return [tag for tag in common_tags if tag.startswith(incomplete)]


def complete_config_keys(incomplete: str) -> List[str]:
    """Auto-complete configuration keys."""
    config_keys = [
        "api_url",
        "api_timeout",
        "default_workflow",
        "project_name",
        "data_retention_days",
        "auto_save_findings",
        "notification_webhook"
    ]
    return [key for key in config_keys if key.startswith(incomplete)]


# Completion callbacks for Typer
WorkflowNameComplete = typer.Option(
    autocompletion=complete_workflow_names,
    help="Workflow name (tab completion available)"
)

RunIdComplete = typer.Option(
    autocompletion=complete_run_ids,
    help="Run ID (tab completion available)"
)

TargetPathComplete = typer.Argument(
    autocompletion=complete_target_paths,
    help="Target path (tab completion available)"
)

ExportFormatComplete = typer.Option(
    autocompletion=complete_export_formats,
    help="Export format (tab completion available)"
)

SeverityComplete = typer.Option(
    autocompletion=complete_severity_levels,
    help="Severity level (tab completion available)"
)

WorkflowTagComplete = typer.Option(
    autocompletion=complete_workflow_tags,
    help="Workflow tag (tab completion available)"
)

ConfigKeyComplete = typer.Option(
    autocompletion=complete_config_keys,
    help="Configuration key (tab completion available)"
)