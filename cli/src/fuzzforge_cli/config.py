"""
Configuration management for FuzzForge CLI.

Extends project configuration with Cognee integration metadata
and provides helpers for AI modules.
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


from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:  # Optional dependency; fall back if not installed
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

import yaml
from pydantic import BaseModel, Field


def _generate_project_id(project_dir: Path, project_name: str) -> str:
    """Generate a deterministic project identifier based on path and name."""
    resolved_path = str(project_dir.resolve())
    hash_input = f"{resolved_path}:{project_name}".encode()
    return hashlib.sha256(hash_input).hexdigest()[:16]


class ProjectConfig(BaseModel):
    """Project configuration model."""

    name: str = "fuzzforge-project"
    api_url: str = "http://localhost:8000"
    default_timeout: int = 3600
    default_workflow: Optional[str] = None
    id: Optional[str] = None
    tenant_id: Optional[str] = None


class RetentionConfig(BaseModel):
    """Data retention configuration."""

    max_runs: int = 100
    keep_findings_days: int = 90


class PreferencesConfig(BaseModel):
    """User preferences."""

    auto_save_findings: bool = True
    show_progress_bars: bool = True
    table_style: str = "rich"
    color_output: bool = True


class WorkerConfig(BaseModel):
    """Worker lifecycle management configuration."""

    auto_start_workers: bool = True
    auto_stop_workers: bool = False
    worker_startup_timeout: int = 60
    docker_compose_file: Optional[str] = None


class CogneeConfig(BaseModel):
    """Cognee integration metadata."""

    enabled: bool = True
    graph_database_provider: str = "kuzu"
    data_directory: Optional[str] = None
    system_directory: Optional[str] = None
    backend_access_control: bool = True
    project_id: Optional[str] = None
    tenant_id: Optional[str] = None


class FuzzForgeConfig(BaseModel):
    """Complete FuzzForge CLI configuration."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    preferences: PreferencesConfig = Field(default_factory=PreferencesConfig)
    workers: WorkerConfig = Field(default_factory=WorkerConfig)
    cognee: CogneeConfig = Field(default_factory=CogneeConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "FuzzForgeConfig":
        """Load configuration from YAML file."""
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            return cls(**data)
        except Exception as exc:  # pragma: no cover - defensive fallback
            print(f"Warning: Failed to load config from {config_path}: {exc}")
            return cls()

    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to YAML file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as fh:
            yaml.dump(
                self.model_dump(),
                fh,
                default_flow_style=False,
                sort_keys=False,
            )

    # ------------------------------------------------------------------
    # Convenience helpers used by CLI and AI modules
    # ------------------------------------------------------------------
    def ensure_project_metadata(self, project_dir: Path) -> bool:
        """Ensure project id/tenant metadata is populated."""
        changed = False
        project = self.project
        if not project.id:
            project.id = _generate_project_id(project_dir, project.name)
            changed = True
        if not project.tenant_id:
            project.tenant_id = f"fuzzforge_project_{project.id}"
            changed = True
        return changed

    def ensure_cognee_defaults(self, project_dir: Path) -> bool:
        """Ensure Cognee configuration and directories exist."""
        self.ensure_project_metadata(project_dir)
        changed = False

        cognee = self.cognee
        if not cognee.project_id:
            cognee.project_id = self.project.id
            changed = True
        if not cognee.tenant_id:
            cognee.tenant_id = self.project.tenant_id
            changed = True

        base_dir = project_dir / ".fuzzforge" / "cognee" / f"project_{self.project.id}"
        data_dir = base_dir / "data"
        system_dir = base_dir / "system"

        for path in (
            base_dir,
            data_dir,
            system_dir,
            system_dir / "kuzu_db",
            system_dir / "lancedb",
        ):
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)

        if cognee.data_directory != str(data_dir):
            cognee.data_directory = str(data_dir)
            changed = True
        if cognee.system_directory != str(system_dir):
            cognee.system_directory = str(system_dir)
            changed = True

        return changed

    def get_api_url(self) -> str:
        """Get API URL with environment variable override."""
        return os.getenv("FUZZFORGE_API_URL", self.project.api_url)

    def get_timeout(self) -> int:
        """Get timeout with environment variable override."""
        env_timeout = os.getenv("FUZZFORGE_TIMEOUT")
        if env_timeout and env_timeout.isdigit():
            return int(env_timeout)
        return self.project.default_timeout

    def get_project_context(self, project_dir: Path) -> Dict[str, str]:
        """Return project metadata for AI integrations."""
        self.ensure_cognee_defaults(project_dir)
        return {
            "project_id": self.project.id or "unknown_project",
            "project_name": self.project.name,
            "tenant_id": self.project.tenant_id or "fuzzforge_tenant",
            "data_directory": self.cognee.data_directory,
            "system_directory": self.cognee.system_directory,
        }

    def get_cognee_config(self, project_dir: Path) -> Dict[str, Any]:
        """Expose Cognee configuration as a plain dictionary."""
        self.ensure_cognee_defaults(project_dir)
        return self.cognee.model_dump()


# ----------------------------------------------------------------------
# Project-level helpers used across the CLI
# ----------------------------------------------------------------------

def _get_project_paths(project_dir: Path) -> Dict[str, Path]:
    config_dir = project_dir / ".fuzzforge"
    return {
        "config_dir": config_dir,
        "config_path": config_dir / "config.yaml",
    }


def get_project_config(project_dir: Optional[Path] = None) -> Optional[FuzzForgeConfig]:
    """Get configuration for the current project."""
    project_dir = Path(project_dir or Path.cwd())
    paths = _get_project_paths(project_dir)
    config_path = paths["config_path"]

    if not config_path.exists():
        return None

    config = FuzzForgeConfig.from_file(config_path)
    if config.ensure_cognee_defaults(project_dir):
        config.save_to_file(config_path)
    return config


def ensure_project_config(
    project_dir: Optional[Path] = None,
    project_name: Optional[str] = None,
    api_url: Optional[str] = None,
) -> FuzzForgeConfig:
    """Ensure project configuration exists, creating defaults if needed."""
    project_dir = Path(project_dir or Path.cwd())
    paths = _get_project_paths(project_dir)
    config_dir = paths["config_dir"]
    config_path = paths["config_path"]

    config_dir.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        config = FuzzForgeConfig.from_file(config_path)
    else:
        config = FuzzForgeConfig()

    if project_name:
        config.project.name = project_name
    if api_url:
        config.project.api_url = api_url

    if config.ensure_cognee_defaults(project_dir):
        config.save_to_file(config_path)
    else:
        # Still ensure latest values persisted (e.g., updated name/url)
        config.save_to_file(config_path)

    return config


def get_global_config() -> FuzzForgeConfig:
    """Get global user configuration."""
    home = Path.home()
    global_config_dir = home / ".config" / "fuzzforge"
    global_config_path = global_config_dir / "config.yaml"

    if global_config_path.exists():
        return FuzzForgeConfig.from_file(global_config_path)

    return FuzzForgeConfig()


def save_global_config(config: FuzzForgeConfig) -> None:
    """Save global user configuration."""
    home = Path.home()
    global_config_dir = home / ".config" / "fuzzforge"
    global_config_path = global_config_dir / "config.yaml"
    config.save_to_file(global_config_path)


# ----------------------------------------------------------------------
# Compatibility layer for AI modules
# ----------------------------------------------------------------------

class ProjectConfigManager:
    """Lightweight wrapper mimicking the legacy Config class used by the AI module."""

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = Path(project_dir or Path.cwd())
        paths = _get_project_paths(self.project_dir)
        self.config_path = paths["config_dir"]
        self.file_path = paths["config_path"]
        self._config = get_project_config(self.project_dir)
        if self._config is None:
            raise FileNotFoundError(
                f"FuzzForge project not initialized in {self.project_dir}. Run 'ff init'."
            )

    # Legacy API ------------------------------------------------------
    def is_initialized(self) -> bool:
        return self.file_path.exists()

    def get_project_context(self) -> Dict[str, str]:
        return self._config.get_project_context(self.project_dir)

    def get_cognee_config(self) -> Dict[str, Any]:
        return self._config.get_cognee_config(self.project_dir)

    def setup_cognee_environment(self) -> None:
        cognee = self.get_cognee_config()
        if not cognee.get("enabled", True):
            return

        # Load project-specific environment overrides from .fuzzforge/.env if available
        env_file = self.project_dir / ".fuzzforge" / ".env"
        if env_file.exists():
            if load_dotenv:
                load_dotenv(env_file, override=False)
            else:
                try:
                    for line in env_file.read_text(encoding="utf-8").splitlines():
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#"):
                            continue
                        if "=" not in stripped:
                            continue
                        key, value = stripped.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
                except Exception:  # pragma: no cover - best effort fallback
                    pass

        backend_access = "true" if cognee.get("backend_access_control", True) else "false"
        os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = backend_access
        os.environ["GRAPH_DATABASE_PROVIDER"] = cognee.get("graph_database_provider", "kuzu")

        data_dir = cognee.get("data_directory")
        system_dir = cognee.get("system_directory")
        tenant_id = cognee.get("tenant_id", "fuzzforge_tenant")

        if data_dir:
            os.environ["COGNEE_DATA_ROOT"] = data_dir
        if system_dir:
            os.environ["COGNEE_SYSTEM_ROOT"] = system_dir
        os.environ["COGNEE_USER_ID"] = tenant_id
        os.environ["COGNEE_TENANT_ID"] = tenant_id

        # Configure LLM provider defaults for Cognee. Values prefixed with COGNEE_
        # take precedence so users can segregate credentials.
        def _env(*names: str, default: str | None = None) -> str | None:
            for name in names:
                value = os.getenv(name)
                if value:
                    return value
            return default

        provider = _env(
            "LLM_COGNEE_PROVIDER",
            "COGNEE_LLM_PROVIDER",
            "LLM_PROVIDER",
            default="openai",
        )
        model = _env(
            "LLM_COGNEE_MODEL",
            "COGNEE_LLM_MODEL",
            "LLM_MODEL",
            "LITELLM_MODEL",
            default="gpt-4o-mini",
        )
        api_key = _env(
            "LLM_COGNEE_API_KEY",
            "COGNEE_LLM_API_KEY",
            "LLM_API_KEY",
            "OPENAI_API_KEY",
        )
        endpoint = _env("LLM_COGNEE_ENDPOINT", "COGNEE_LLM_ENDPOINT", "LLM_ENDPOINT")
        api_version = _env(
            "LLM_COGNEE_API_VERSION",
            "COGNEE_LLM_API_VERSION",
            "LLM_API_VERSION",
        )
        max_tokens = _env(
            "LLM_COGNEE_MAX_TOKENS",
            "COGNEE_LLM_MAX_TOKENS",
            "LLM_MAX_TOKENS",
        )

        if provider:
            os.environ["LLM_PROVIDER"] = provider
        if model:
            os.environ["LLM_MODEL"] = model
            # Maintain backwards compatibility with components expecting LITELLM_MODEL
            os.environ.setdefault("LITELLM_MODEL", model)
        if api_key:
            os.environ["LLM_API_KEY"] = api_key
            # Provide OPENAI_API_KEY fallback when using OpenAI-compatible providers
            if provider and provider.lower() in {"openai", "azure_openai", "custom"}:
                os.environ.setdefault("OPENAI_API_KEY", api_key)
        if endpoint:
            os.environ["LLM_ENDPOINT"] = endpoint
        if api_version:
            os.environ["LLM_API_VERSION"] = api_version
        if max_tokens:
            os.environ["LLM_MAX_TOKENS"] = str(max_tokens)

        # FuzzForge MCP backend connection - fallback if not in .env
        if not os.getenv("FUZZFORGE_MCP_URL"):
            os.environ["FUZZFORGE_MCP_URL"] = os.getenv(
                "FUZZFORGE_DEFAULT_MCP_URL",
                "http://localhost:8010/mcp",
            )

    def refresh(self) -> None:
        """Reload configuration from disk."""
        self._config = get_project_config(self.project_dir)
        if self._config is None:
            raise FileNotFoundError(
                f"FuzzForge project not initialized in {self.project_dir}. Run 'ff init'."
            )

    # Convenience accessors ------------------------------------------
    @property
    def fuzzforge_dir(self) -> Path:
        return self.config_path

    def get_api_url(self) -> str:
        return self._config.get_api_url()

    def get_timeout(self) -> int:
        return self._config.get_timeout()
