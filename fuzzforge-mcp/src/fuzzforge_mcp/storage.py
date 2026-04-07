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
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from tarfile import open as Archive  # noqa: N812
from typing import Any
from uuid import uuid4

import yaml

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
        (storage_path / "output").mkdir(parents=True, exist_ok=True)

        # Create .gitignore to avoid committing large files
        gitignore_path = storage_path / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(
                "# FuzzForge storage - ignore large/temporary files\n"
                "runs/\n"
                "output/\n"
                "artifacts.json\n"
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

    def get_project_output_path(self, project_path: Path) -> Path | None:
        """Get the output directory path for a project.

        Returns the path to the writable output directory that is mounted
        into hub tool containers at /app/output.

        :param project_path: Path to the project directory.
        :returns: Path to output directory, or None if project not initialized.

        """
        output_path = self._get_project_path(project_path) / "output"
        if output_path.exists():
            return output_path
        return None

    def record_execution(
        self,
        project_path: Path,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        """Record an execution result to the project's runs directory.

        :param project_path: Path to the project directory.
        :param server_name: Hub server name.
        :param tool_name: Tool name that was executed.
        :param arguments: Arguments passed to the tool.
        :param result: Execution result dictionary.
        :returns: Execution ID.

        """
        execution_id = f"{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
        run_dir = self._get_project_path(project_path) / "runs" / execution_id
        run_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "execution_id": execution_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
            "success": result.get("success", False),
            "result": result,
        }
        (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))

        logger.info("Recorded execution %s: %s:%s", execution_id, server_name, tool_name)
        return execution_id

    def list_executions(self, project_path: Path) -> list[dict[str, Any]]:
        """List all executions for a project with summary metadata.

        :param project_path: Path to the project directory.
        :returns: List of execution summaries (id, timestamp, server, tool, success).

        """
        runs_dir = self._get_project_path(project_path) / "runs"
        if not runs_dir.exists():
            return []

        executions: list[dict[str, Any]] = []
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                executions.append({
                    "execution_id": meta.get("execution_id", run_dir.name),
                    "timestamp": meta.get("timestamp"),
                    "server": meta.get("server"),
                    "tool": meta.get("tool"),
                    "success": meta.get("success"),
                })
            else:
                executions.append({"execution_id": run_dir.name})
        return executions

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

    # ------------------------------------------------------------------
    # Artifact tracking
    # ------------------------------------------------------------------

    def _artifacts_path(self, project_path: Path) -> Path:
        """Get the path to the artifacts registry file.

        :param project_path: Path to the project directory.
        :returns: Path to artifacts.json.

        """
        return self._get_project_path(project_path) / "artifacts.json"

    def _load_artifacts(self, project_path: Path) -> list[dict[str, Any]]:
        """Load the artifact registry from disk.

        :param project_path: Path to the project directory.
        :returns: List of artifact dicts.

        """
        path = self._artifacts_path(project_path)
        if path.exists():
            try:
                return json.loads(path.read_text())  # type: ignore[no-any-return]
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_artifacts(self, project_path: Path, artifacts: list[dict[str, Any]]) -> None:
        """Persist the artifact registry to disk.

        :param project_path: Path to the project directory.
        :param artifacts: Full artifact list to write.

        """
        path = self._artifacts_path(project_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifacts, indent=2, default=str))

    def _classify_file(self, file_path: Path) -> str:
        """Classify a file into a human-friendly type string.

        :param file_path: Path to the file.
        :returns: Type string (e.g. "elf-binary", "text", "directory").

        """
        mime, _ = mimetypes.guess_type(str(file_path))
        suffix = file_path.suffix.lower()

        # Try reading ELF magic for binaries with no extension
        if mime is None and suffix == "":
            try:
                header = file_path.read_bytes()[:4]
                if header == b"\x7fELF":
                    return "elf-binary"
            except OSError:
                pass

        if mime:
            if "json" in mime:
                return "json"
            if "text" in mime or "xml" in mime or "yaml" in mime:
                return "text"
            if "image" in mime:
                return "image"
            if "octet-stream" in mime:
                return "binary"

        type_map: dict[str, str] = {
            ".json": "json",
            ".sarif": "sarif",
            ".md": "markdown",
            ".txt": "text",
            ".log": "text",
            ".csv": "csv",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".html": "html",
            ".elf": "elf-binary",
            ".so": "elf-binary",
            ".bin": "binary",
            ".gz": "archive",
            ".tar": "archive",
            ".zip": "archive",
        }
        return type_map.get(suffix, "binary")

    def scan_artifacts(
        self,
        project_path: Path,
        server_name: str,
        tool_name: str,
    ) -> list[dict[str, Any]]:
        """Scan the output directory for new or modified files and register them.

        Compares the current state of .fuzzforge/output/ against the existing
        artifact registry and registers any new or modified files.

        :param project_path: Path to the project directory.
        :param server_name: Hub server that produced the artifacts.
        :param tool_name: Tool that produced the artifacts.
        :returns: List of newly registered artifact dicts.

        """
        output_path = self.get_project_output_path(project_path)
        if output_path is None or not output_path.exists():
            return []

        existing = self._load_artifacts(project_path)
        known: dict[str, dict[str, Any]] = {a["path"]: a for a in existing}
        now = datetime.now(tz=UTC).isoformat()

        new_artifacts: list[dict[str, Any]] = []
        for file_path in output_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Use the container-style path (/app/output/...) so it's
            # directly usable in subsequent tool calls.
            relative = file_path.relative_to(output_path)
            container_path = f"/app/output/{relative}"

            stat = file_path.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()

            prev = known.get(container_path)
            if prev and prev.get("mtime") == mtime and prev.get("size") == size:
                continue  # Unchanged — skip

            artifact: dict[str, Any] = {
                "path": container_path,
                "host_path": str(file_path),
                "type": self._classify_file(file_path),
                "size": size,
                "mtime": mtime,
                "source_server": server_name,
                "source_tool": tool_name,
                "registered_at": now,
            }

            if prev:
                # Update existing entry in-place
                idx = next(i for i, a in enumerate(existing) if a["path"] == container_path)
                existing[idx] = artifact
            else:
                existing.append(artifact)

            new_artifacts.append(artifact)

        if new_artifacts:
            self._save_artifacts(project_path, existing)
            logger.info(
                "Registered %d new artifact(s) from %s:%s",
                len(new_artifacts),
                server_name,
                tool_name,
            )

        return new_artifacts

    def list_artifacts(
        self,
        project_path: Path,
        *,
        source: str | None = None,
        artifact_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List registered artifacts, with optional filters.

        :param project_path: Path to the project directory.
        :param source: Filter by source server name.
        :param artifact_type: Filter by artifact type (e.g. "elf-binary", "json").
        :returns: List of matching artifact dicts.

        """
        artifacts = self._load_artifacts(project_path)

        if source:
            artifacts = [a for a in artifacts if a.get("source_server") == source]
        if artifact_type:
            artifacts = [a for a in artifacts if a.get("type") == artifact_type]

        return artifacts

    def get_artifact(self, project_path: Path, path: str) -> dict[str, Any] | None:
        """Get a single artifact by its container path.

        :param project_path: Path to the project directory.
        :param path: Container path of the artifact (e.g. /app/output/...).
        :returns: Artifact dict, or None if not found.

        """
        artifacts = self._load_artifacts(project_path)
        for artifact in artifacts:
            if artifact["path"] == path:
                return artifact
        return None

    # ------------------------------------------------------------------
    # Skill packs
    # ------------------------------------------------------------------

    #: Directory containing built-in skill packs shipped with FuzzForge.
    _BUILTIN_SKILLS_DIR: Path = Path(__file__).parent / "skills"

    def _skill_dirs(self, project_path: Path) -> list[Path]:
        """Return skill directories in priority order (project-local first).

        :param project_path: Path to the project directory.
        :returns: List of directories that may contain skill YAML files.

        """
        dirs: list[Path] = []
        project_skills = self._get_project_path(project_path) / "skills"
        if project_skills.is_dir():
            dirs.append(project_skills)
        if self._BUILTIN_SKILLS_DIR.is_dir():
            dirs.append(self._BUILTIN_SKILLS_DIR)
        return dirs

    def list_skills(self, project_path: Path) -> list[dict[str, Any]]:
        """List available skill packs from project and built-in directories.

        :param project_path: Path to the project directory.
        :returns: List of skill summaries (name, description first line, source).

        """
        seen: set[str] = set()
        skills: list[dict[str, Any]] = []

        for skill_dir in self._skill_dirs(project_path):
            for yaml_path in sorted(skill_dir.glob("*.yaml")):
                skill = self._parse_skill_file(yaml_path)
                if skill is None:
                    continue
                name = skill["name"]
                if name in seen:
                    continue  # project-local overrides built-in
                seen.add(name)
                desc = skill.get("description", "")
                first_line = desc.strip().split("\n", 1)[0] if desc else ""
                is_project = ".fuzzforge" in str(yaml_path.parent)
                source = "project" if is_project else "builtin"
                skills.append({
                    "name": name,
                    "summary": first_line,
                    "source": source,
                    "servers": skill.get("servers", []),
                })

        return skills

    def load_skill(self, project_path: Path, name: str) -> dict[str, Any] | None:
        """Load a skill pack by name.

        Searches project-local skills first, then built-in skills.

        :param project_path: Path to the project directory.
        :param name: Skill name (filename without .yaml extension).
        :returns: Parsed skill dict with name, description, servers — or None.

        """
        for skill_dir in self._skill_dirs(project_path):
            yaml_path = skill_dir / f"{name}.yaml"
            if yaml_path.is_file():
                return self._parse_skill_file(yaml_path)
        return None

    @staticmethod
    def _parse_skill_file(yaml_path: Path) -> dict[str, Any] | None:
        """Parse and validate a skill YAML file.

        :param yaml_path: Path to the YAML file.
        :returns: Parsed skill dict, or None if invalid.

        """
        try:
            data = yaml.safe_load(yaml_path.read_text())
        except (yaml.YAMLError, OSError):
            logger.warning("Failed to parse skill file: %s", yaml_path)
            return None

        if not isinstance(data, dict):
            return None

        name = data.get("name")
        if not name or not isinstance(name, str):
            logger.warning("Skill file missing 'name': %s", yaml_path)
            return None

        return {
            "name": name,
            "description": data.get("description", ""),
            "servers": data.get("servers", []),
        }
