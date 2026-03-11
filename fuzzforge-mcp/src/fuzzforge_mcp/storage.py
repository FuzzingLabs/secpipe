"""FuzzForge MCP Server - Local project storage.

Lightweight project storage for managing `.fuzzforge/` directories,
execution results, and project configuration. Extracted from the
former fuzzforge-runner storage module.

Storage is placed directly in the project directory as `.fuzzforge/`
for maximum visibility and ease of debugging.

"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from tarfile import open as Archive  # noqa: N812
from typing import Any

logger = logging.getLogger("fuzzforge-mcp")

#: Name of the FuzzForge storage directory within projects.
FUZZFORGE_DIR_NAME: str = ".fuzzforge"

#: Standard results archive filename.
RESULTS_ARCHIVE_FILENAME: str = "results.tar.gz"


class StorageError(Exception):
    """Raised when a storage operation fails."""


class LocalStorage:
    """Local filesystem storage backend for FuzzForge.

    Provides lightweight storage for project configuration and
    execution results tracking.

    Directory structure (inside project directory)::

        {project_path}/.fuzzforge/
            config.json             # Project config (source path reference)
            runs/                   # Execution results
                {execution_id}/
                    results.tar.gz

    """

    _base_path: Path

    def __init__(self, base_path: Path) -> None:
        """Initialize storage backend.

        :param base_path: Root directory for global storage (fallback).

        """
        self._base_path = base_path
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _get_project_path(self, project_path: Path) -> Path:
        """Get the .fuzzforge storage path for a project.

        :param project_path: Path to the project directory.
        :returns: Storage path (.fuzzforge inside project).

        """
        return project_path / FUZZFORGE_DIR_NAME

    def init_project(self, project_path: Path) -> Path:
        """Initialize storage for a new project.

        Creates a .fuzzforge/ directory inside the project for storing
        configuration and execution results.

        :param project_path: Path to the project directory.
        :returns: Path to the project storage directory.

        """
        storage_path = self._get_project_path(project_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        (storage_path / "runs").mkdir(parents=True, exist_ok=True)

        # Create .gitignore to avoid committing large files
        gitignore_path = storage_path / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(
                "# FuzzForge storage - ignore large/temporary files\n"
                "runs/\n"
                "!config.json\n"
            )

        logger.info("Initialized project storage: %s", storage_path)
        return storage_path

    def get_project_assets_path(self, project_path: Path) -> Path | None:
        """Get the configured source path for a project.

        :param project_path: Path to the project directory.
        :returns: Path to source directory, or None if not configured.

        """
        storage_path = self._get_project_path(project_path)
        config_path = storage_path / "config.json"

        if config_path.exists():
            config = json.loads(config_path.read_text())
            source_path = config.get("source_path")
            if source_path:
                path = Path(source_path)
                if path.exists():
                    return path

        return None

    def set_project_assets(self, project_path: Path, assets_path: Path) -> Path:
        """Set the source path for a project (reference only, no copying).

        :param project_path: Path to the project directory.
        :param assets_path: Path to source directory.
        :returns: The assets path (unchanged).
        :raises StorageError: If path doesn't exist.

        """
        if not assets_path.exists():
            msg = f"Assets path does not exist: {assets_path}"
            raise StorageError(msg)

        assets_path = assets_path.resolve()

        storage_path = self._get_project_path(project_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        config_path = storage_path / "config.json"

        config: dict[str, Any] = {}
        if config_path.exists():
            config = json.loads(config_path.read_text())

        config["source_path"] = str(assets_path)
        config_path.write_text(json.dumps(config, indent=2))

        logger.info("Set project assets: %s -> %s", project_path.name, assets_path)
        return assets_path

    def list_executions(self, project_path: Path) -> list[str]:
        """List all execution IDs for a project.

        :param project_path: Path to the project directory.
        :returns: List of execution IDs.

        """
        runs_dir = self._get_project_path(project_path) / "runs"
        if not runs_dir.exists():
            return []
        return [d.name for d in runs_dir.iterdir() if d.is_dir()]

    def get_execution_results(
        self,
        project_path: Path,
        execution_id: str,
    ) -> Path | None:
        """Retrieve execution results path.

        :param project_path: Path to the project directory.
        :param execution_id: Execution ID.
        :returns: Path to results archive, or None if not found.

        """
        storage_path = self._get_project_path(project_path)

        # Try direct path
        results_path = storage_path / "runs" / execution_id / RESULTS_ARCHIVE_FILENAME
        if results_path.exists():
            return results_path

        # Search in all run directories
        runs_dir = storage_path / "runs"
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                if run_dir.is_dir() and execution_id in run_dir.name:
                    candidate = run_dir / RESULTS_ARCHIVE_FILENAME
                    if candidate.exists():
                        return candidate

        return None

    def extract_results(self, results_path: Path, destination: Path) -> Path:
        """Extract a results archive to a destination directory.

        :param results_path: Path to the results archive.
        :param destination: Directory to extract to.
        :returns: Path to extracted directory.
        :raises StorageError: If extraction fails.

        """
        try:
            destination.mkdir(parents=True, exist_ok=True)
            with Archive(results_path, "r:gz") as tar:
                tar.extractall(path=destination)  # noqa: S202
            logger.info("Extracted results: %s -> %s", results_path, destination)
            return destination
        except Exception as exc:
            msg = f"Failed to extract results: {exc}"
            raise StorageError(msg) from exc
