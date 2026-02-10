"""FuzzForge Runner - Local filesystem storage.

This module provides local filesystem storage for OSS deployments.

Storage is placed directly in the project directory as `.fuzzforge/`
for maximum visibility and ease of debugging.

In OSS mode, source files are referenced (not copied) and mounted
directly into containers at runtime for zero-copy performance.

"""

from __future__ import annotations

import shutil
from pathlib import Path
from tarfile import open as Archive  # noqa: N812
from typing import TYPE_CHECKING, cast

from fuzzforge_runner.constants import RESULTS_ARCHIVE_FILENAME
from fuzzforge_runner.exceptions import StorageError

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

#: Name of the FuzzForge storage directory within projects.
FUZZFORGE_DIR_NAME: str = ".fuzzforge"


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


class LocalStorage:
    """Local filesystem storage backend for FuzzForge OSS.

    Provides lightweight storage for execution results while using
    direct source mounting (no copying) for input assets.

    Storage is placed directly in the project directory as `.fuzzforge/`
    so users can easily inspect outputs and configuration.

    Directory structure (inside project directory):
        {project_path}/.fuzzforge/
            config.json             # Project config (source path reference)
            runs/                   # Execution results
                {execution_id}/
                    results.tar.gz
                {workflow_id}/
                    modules/
                        step-0-{exec_id}/
                            results.tar.gz

    Source files are NOT copied - they are referenced and mounted directly.

    """

    #: Base path for global storage (only used for fallback/config).
    _base_path: Path

    def __init__(self, base_path: Path) -> None:
        """Initialize an instance of the class.

        :param base_path: Root directory for global storage (fallback only).

        """
        self._base_path = base_path
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """Ensure the base storage directory exists."""
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _get_project_path(self, project_path: Path) -> Path:
        """Get the storage path for a project.

        Storage is placed directly inside the project as `.fuzzforge/`.

        :param project_path: Path to the project directory.
        :returns: Storage path for the project (.fuzzforge inside project).

        """
        return project_path / FUZZFORGE_DIR_NAME

    def init_project(self, project_path: Path) -> Path:
        """Initialize storage for a new project.

        Creates a .fuzzforge/ directory inside the project for storing:
        - assets/: Input files (source code, etc.)
        - inputs/: Prepared module inputs (for debugging)
        - runs/: Execution results from each module

        :param project_path: Path to the project directory.
        :returns: Path to the project storage directory.

        """
        logger = get_logger()
        storage_path = self._get_project_path(project_path)

        # Create directory structure (minimal for OSS)
        storage_path.mkdir(parents=True, exist_ok=True)
        (storage_path / "runs").mkdir(parents=True, exist_ok=True)

        # Create .gitignore to avoid committing large files
        gitignore_path = storage_path / ".gitignore"
        if not gitignore_path.exists():
            gitignore_content = """# FuzzForge storage - ignore large/temporary files
# Execution results (can be very large)
runs/

# Project configuration
!config.json
"""
            gitignore_path.write_text(gitignore_content)

        logger.info("initialized project storage", project=project_path.name, storage=str(storage_path))

        return storage_path

    def get_project_assets_path(self, project_path: Path) -> Path | None:
        """Get the path to project assets (source directory).

        Returns the configured source path for the project.
        In OSS mode, this is just a reference to the user's source - no copying.

        :param project_path: Path to the project directory.
        :returns: Path to source directory, or None if not configured.

        """
        storage_path = self._get_project_path(project_path)
        config_path = storage_path / "config.json"

        if config_path.exists():
            import json
            config = json.loads(config_path.read_text())
            source_path = config.get("source_path")
            if source_path:
                path = Path(source_path)
                if path.exists():
                    return path

        # Fallback: check if project_path itself is the source
        # (common case: user runs from their project directory)
        if (project_path / "Cargo.toml").exists() or (project_path / "src").exists():
            return project_path

        return None

    def set_project_assets(self, project_path: Path, assets_path: Path) -> Path:
        """Set the source path for a project (no copying).

        Just stores a reference to the source directory.
        The source is mounted directly into containers at runtime.

        :param project_path: Path to the project directory.
        :param assets_path: Path to source directory.
        :returns: The assets path (unchanged).
        :raises StorageError: If path doesn't exist.

        """
        import json

        logger = get_logger()

        if not assets_path.exists():
            raise StorageError(f"Assets path does not exist: {assets_path}")

        # Resolve to absolute path
        assets_path = assets_path.resolve()

        # Store reference in config
        storage_path = self._get_project_path(project_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        config_path = storage_path / "config.json"

        config: dict = {}
        if config_path.exists():
            config = json.loads(config_path.read_text())

        config["source_path"] = str(assets_path)
        config_path.write_text(json.dumps(config, indent=2))

        logger.info("set project assets", project=project_path.name, source=str(assets_path))
        return assets_path

    def store_execution_results(
        self,
        project_path: Path,
        workflow_id: str | None,
        step_index: int,
        execution_id: str,
        results_path: Path,
    ) -> Path:
        """Store execution results.

        :param project_path: Path to the project directory.
        :param workflow_id: Workflow execution ID (None for standalone).
        :param step_index: Step index in workflow.
        :param execution_id: Module execution ID.
        :param results_path: Path to results archive to store.
        :returns: Path to the stored results.
        :raises StorageError: If storage operation fails.

        """
        logger = get_logger()
        storage_path = self._get_project_path(project_path)

        try:
            if workflow_id:
                # Part of workflow
                dest_dir = storage_path / "runs" / workflow_id / "modules" / f"step-{step_index}-{execution_id}"
            else:
                # Standalone execution
                dest_dir = storage_path / "runs" / execution_id

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / RESULTS_ARCHIVE_FILENAME

            shutil.copy2(results_path, dest_path)

            logger.info(
                "stored execution results",
                execution_id=execution_id,
                path=str(dest_path),
            )

            return dest_path

        except Exception as exc:
            message = f"Failed to store results: {exc}"
            raise StorageError(message) from exc

    def get_execution_results(
        self,
        project_path: Path,
        execution_id: str,
        workflow_id: str | None = None,
        step_index: int | None = None,
    ) -> Path | None:
        """Retrieve execution results.

        :param project_path: Path to the project directory.
        :param execution_id: Module execution ID.
        :param workflow_id: Workflow execution ID (None for standalone).
        :param step_index: Step index in workflow.
        :returns: Path to results archive, or None if not found.

        """
        storage_path = self._get_project_path(project_path)

        if workflow_id and step_index is not None:
            # Direct workflow path lookup
            results_path = (
                storage_path / "runs" / workflow_id / "modules" / f"step-{step_index}-{execution_id}" / RESULTS_ARCHIVE_FILENAME
            )
            if results_path.exists():
                return results_path
        
        # Try standalone path
        results_path = storage_path / "runs" / execution_id / RESULTS_ARCHIVE_FILENAME
        if results_path.exists():
            return results_path
        
        # Search for execution_id in all workflow runs
        runs_dir = storage_path / "runs"
        if runs_dir.exists():
            for workflow_dir in runs_dir.iterdir():
                if not workflow_dir.is_dir():
                    continue
                
                # Check if this is a workflow directory (has 'modules' subdirectory)
                modules_dir = workflow_dir / "modules"
                if modules_dir.exists() and modules_dir.is_dir():
                    # Search for step directories containing this execution_id
                    for step_dir in modules_dir.iterdir():
                        if step_dir.is_dir() and execution_id in step_dir.name:
                            results_path = step_dir / RESULTS_ARCHIVE_FILENAME
                            if results_path.exists():
                                return results_path

        return None

    def list_executions(self, project_path: Path) -> list[str]:
        """List all execution IDs for a project.

        :param project_path: Path to the project directory.
        :returns: List of execution IDs.

        """
        storage_path = self._get_project_path(project_path)
        runs_dir = storage_path / "runs"

        if not runs_dir.exists():
            return []

        return [d.name for d in runs_dir.iterdir() if d.is_dir()]

    def delete_execution(self, project_path: Path, execution_id: str) -> bool:
        """Delete an execution and its results.

        :param project_path: Path to the project directory.
        :param execution_id: Execution ID to delete.
        :returns: True if deleted, False if not found.

        """
        logger = get_logger()
        storage_path = self._get_project_path(project_path)
        exec_path = storage_path / "runs" / execution_id

        if exec_path.exists():
            shutil.rmtree(exec_path)
            logger.info("deleted execution", execution_id=execution_id)
            return True

        return False

    def delete_project(self, project_path: Path) -> bool:
        """Delete all storage for a project.

        :param project_path: Path to the project directory.
        :returns: True if deleted, False if not found.

        """
        logger = get_logger()
        storage_path = self._get_project_path(project_path)

        if storage_path.exists():
            shutil.rmtree(storage_path)
            logger.info("deleted project storage", project=project_path.name)
            return True

        return False

    def extract_results(self, results_path: Path, destination: Path) -> Path:
        """Extract a results archive to a destination directory.

        :param results_path: Path to the results archive.
        :param destination: Directory to extract to.
        :returns: Path to extracted directory.
        :raises StorageError: If extraction fails.

        """
        logger = get_logger()

        try:
            destination.mkdir(parents=True, exist_ok=True)

            with Archive(results_path, "r:gz") as tar:
                tar.extractall(path=destination)

            logger.info("extracted results", source=str(results_path), destination=str(destination))
            return destination

        except Exception as exc:
            message = f"Failed to extract results: {exc}"
            raise StorageError(message) from exc
