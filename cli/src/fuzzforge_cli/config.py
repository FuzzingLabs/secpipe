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
from typing import Any, Dict, Optional, Literal

try:  # Optional dependency; fall back if not installed
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def _load_env_file_if_exists(path: Path, override: bool = False) -> bool:
    if not path.exists():
        return False
    # Always use manual parsing to handle empty values correctly
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()
            if override:
                # Only override if value is non-empty
                if value:
                    os.environ[key] = value
            else:
                # Set if not already in environment and value is non-empty
                if key not in os.environ and value:
                    os.environ[key] = value
        return True
    except Exception:  # pragma: no cover - best effort fallback
        return False


def _find_shared_env_file(project_dir: Path) -> Path | None:
    for directory in [project_dir] + list(project_dir.parents):
        candidate = directory / "volumes" / "env" / ".env"
        if candidate.exists():
            return candidate
    return None


def load_project_env(project_dir: Optional[Path] = None) -> Path | None:
    """Load project-local env, falling back to shared volumes/env/.env."""

    project_dir = Path(project_dir or Path.cwd())
    shared_env = _find_shared_env_file(project_dir)
    loaded_shared = False
    if shared_env:
        loaded_shared = _load_env_file_if_exists(shared_env, override=False)

    project_env = project_dir / ".fuzzforge" / ".env"
    if _load_env_file_if_exists(project_env, override=True):
        return project_env

    if loaded_shared:
        return shared_env

    return None

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
    graph_database_provider: str = "ladybug"
    service_url: str = "http://localhost:18000"
    api_key: Optional[str] = None
    service_email: Optional[str] = None
    service_password: Optional[str] = None
    storage_backend: Literal["local", "s3"] = "s3"
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = "projects"
    s3_endpoint_url: Optional[str] = None
    s3_region: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_allow_http: bool = False
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

        if not cognee.service_url:
            cognee.service_url = "http://localhost:18000"
            changed = True

        if not cognee.s3_prefix:
            cognee.s3_prefix = "projects"
            changed = True

        default_email = f"project_{self.project.id}@fuzzforge.dev"
        if not cognee.service_email or cognee.service_email.endswith(
            ("@cognee.local", "@cognee.localhost")
        ):
            cognee.service_email = default_email
            changed = True

        derived_password = hashlib.sha256(self.project.id.encode()).hexdigest()[:20]
        if not cognee.service_password or len(cognee.service_password) < 12:
            cognee.service_password = derived_password
            changed = True

        if cognee.storage_backend.lower() == "s3":
            bucket = cognee.s3_bucket or "cognee"
            prefix = (cognee.s3_prefix or "projects").strip("/")
            base_uri = f"s3://{bucket}/{prefix}/{self.project.id}"
            data_dir = f"{base_uri}/files"
            system_dir = f"{base_uri}/graph"
        else:
            base_dir = project_dir / ".fuzzforge" / "cognee" / f"project_{self.project.id}"
            data_path = base_dir / "data"
            system_path = base_dir / "system"

            for path in (
                base_dir,
                data_path,
                system_path,
                system_path / "ladybug",
                system_path / "lancedb",
            ):
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)

            data_dir = str(data_path)
            system_dir = str(system_path)

        if cognee.data_directory != data_dir:
            cognee.data_directory = data_dir
            changed = True
        if cognee.system_directory != system_dir:
            cognee.system_directory = system_dir
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

        load_project_env(self.project_dir)

        backend_access = "true" if cognee.get("backend_access_control", True) else "false"
        os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = backend_access
        graph_provider = cognee.get("graph_database_provider", "ladybug")
        os.environ["GRAPH_DATABASE_PROVIDER"] = graph_provider

        service_url = cognee.get("service_url") or os.getenv("COGNEE_SERVICE_URL") or "http://localhost:18000"
        os.environ["COGNEE_SERVICE_URL"] = service_url
        api_key = os.getenv("COGNEE_API_KEY") or cognee.get("api_key")
        if api_key:
            os.environ["COGNEE_API_KEY"] = api_key
        service_email = os.getenv("COGNEE_SERVICE_EMAIL") or cognee.get("service_email")
        if service_email:
            os.environ["COGNEE_SERVICE_EMAIL"] = service_email
        service_password = os.getenv("COGNEE_SERVICE_PASSWORD") or cognee.get("service_password")
        if service_password:
            os.environ["COGNEE_SERVICE_PASSWORD"] = service_password

        data_dir = cognee.get("data_directory")
        system_dir = cognee.get("system_directory")
        tenant_id = cognee.get("tenant_id", "fuzzforge_tenant")
        storage_backend = cognee.get("storage_backend", "local").lower()
        os.environ["COGNEE_STORAGE_BACKEND"] = storage_backend

        if storage_backend == "s3":
            os.environ["STORAGE_BACKEND"] = "s3"

            bucket = os.getenv("COGNEE_S3_BUCKET") or cognee.get("s3_bucket") or "cognee"
            os.environ["STORAGE_BUCKET_NAME"] = bucket
            os.environ["COGNEE_S3_BUCKET"] = bucket

            prefix_override = os.getenv("COGNEE_S3_PREFIX") or cognee.get("s3_prefix")
            if prefix_override:
                os.environ["COGNEE_S3_PREFIX"] = prefix_override

            endpoint = os.getenv("COGNEE_S3_ENDPOINT") or cognee.get("s3_endpoint_url") or "http://localhost:9000"
            os.environ["AWS_ENDPOINT_URL"] = endpoint
            os.environ["COGNEE_S3_ENDPOINT"] = endpoint

            region = os.getenv("COGNEE_S3_REGION") or cognee.get("s3_region") or "us-east-1"
            os.environ["AWS_REGION"] = region
            os.environ["COGNEE_S3_REGION"] = region

            access_key = os.getenv("COGNEE_S3_ACCESS_KEY") or cognee.get("s3_access_key")
            secret_key = os.getenv("COGNEE_S3_SECRET_KEY") or cognee.get("s3_secret_key")
            if access_key:
                os.environ.setdefault("AWS_ACCESS_KEY_ID", access_key)
                os.environ["COGNEE_S3_ACCESS_KEY"] = access_key
            if secret_key:
                os.environ.setdefault("AWS_SECRET_ACCESS_KEY", secret_key)
                os.environ["COGNEE_S3_SECRET_KEY"] = secret_key

            allow_http_env = os.getenv("COGNEE_S3_ALLOW_HTTP")
            allow_http_flag = allow_http_env if allow_http_env is not None else ("true" if cognee.get("s3_allow_http") else "false")
            if allow_http_flag.lower() in {"1", "true", "yes"}:
                os.environ["AWS_ALLOW_HTTP"] = "true"
                os.environ["COGNEE_S3_ALLOW_HTTP"] = "1"

        if data_dir:
            os.environ["COGNEE_DATA_ROOT"] = data_dir
            os.environ.setdefault("DATA_ROOT_DIRECTORY", data_dir)
        if system_dir:
            os.environ["COGNEE_SYSTEM_ROOT"] = system_dir
            os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", system_dir)
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
        embedding_model = _env(
            "LLM_COGNEE_EMBEDDING_MODEL",
            "COGNEE_LLM_EMBEDDING_MODEL",
            "LLM_EMBEDDING_MODEL",
        )
        embedding_endpoint = _env(
            "LLM_COGNEE_EMBEDDING_ENDPOINT",
            "COGNEE_LLM_EMBEDDING_ENDPOINT",
            "LLM_EMBEDDING_ENDPOINT",
            "LLM_ENDPOINT",
        )
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
            os.environ.setdefault("LLM_API_BASE", endpoint)
            os.environ.setdefault("LLM_EMBEDDING_ENDPOINT", endpoint)
            os.environ.setdefault("LLM_EMBEDDING_API_BASE", endpoint)
            os.environ.setdefault("OPENAI_API_BASE", endpoint)
            # Set LiteLLM proxy environment variables for SDK usage
            os.environ.setdefault("LITELLM_PROXY_API_BASE", endpoint)
        if api_key:
            # Set LiteLLM proxy API key from the virtual key
            os.environ.setdefault("LITELLM_PROXY_API_KEY", api_key)
        if embedding_model:
            os.environ["LLM_EMBEDDING_MODEL"] = embedding_model
        if embedding_endpoint:
            os.environ["LLM_EMBEDDING_ENDPOINT"] = embedding_endpoint
            os.environ.setdefault("LLM_EMBEDDING_API_BASE", embedding_endpoint)
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
