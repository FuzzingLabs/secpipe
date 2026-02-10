"""FuzzForge Runner settings configuration."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineType(StrEnum):
    """Supported container engine types."""

    DOCKER = "docker"
    PODMAN = "podman"


class EngineSettings(BaseModel):
    """Container engine configuration."""

    #: Type of container engine to use. Docker is the default for simplicity.
    type: EngineType = EngineType.DOCKER

    #: Path to the container engine socket (only used as fallback for socket-based engines).
    socket: str = Field(default="")

    #: Custom graph root for Podman storage (only used with Podman under Snap).
    graphroot: Path = Field(default=Path.home() / ".fuzzforge" / "containers" / "storage")

    #: Custom run root for Podman runtime state (only used with Podman under Snap).
    runroot: Path = Field(default=Path.home() / ".fuzzforge" / "containers" / "run")


class StorageSettings(BaseModel):
    """Storage configuration for local filesystem storage.

    OSS uses direct file mounting without archiving for simplicity.
    """

    #: Base path for local storage.
    path: Path = Field(default=Path.home() / ".fuzzforge" / "storage")


class ProjectSettings(BaseModel):
    """Project configuration."""

    #: Default path for FuzzForge projects.
    default_path: Path = Field(default=Path.home() / ".fuzzforge" / "projects")


class RegistrySettings(BaseModel):
    """Container registry configuration for module images.

    By default, registry URL is empty (local-only mode). When empty,
    modules must be built locally with `make build-modules`.
    Set via FUZZFORGE_REGISTRY__URL environment variable if needed.
    """

    #: Registry URL for pulling module images (empty = local-only mode).
    url: str = Field(default="")

    #: Default tag to use when pulling images.
    default_tag: str = Field(default="latest")

    #: Registry username for authentication (optional).
    username: str | None = None

    #: Registry password/token for authentication (optional).
    password: str | None = None


class Settings(BaseSettings):
    """FuzzForge Runner settings.

    Settings can be configured via environment variables with the prefix
    ``FUZZFORGE_``. Nested settings use underscore as delimiter.

    Example:
        ``FUZZFORGE_ENGINE_TYPE=docker``
        ``FUZZFORGE_STORAGE_PATH=/data/fuzzforge``
        ``FUZZFORGE_MODULES_PATH=/path/to/modules``

    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="FUZZFORGE_",
    )

    #: Container engine settings.
    engine: EngineSettings = Field(default_factory=EngineSettings)

    #: Storage settings.
    storage: StorageSettings = Field(default_factory=StorageSettings)

    #: Project settings.
    project: ProjectSettings = Field(default_factory=ProjectSettings)

    #: Container registry settings.
    registry: RegistrySettings = Field(default_factory=RegistrySettings)

    #: Path to modules directory (for development/local builds).
    modules_path: Path = Field(default=Path.home() / ".fuzzforge" / "modules")

    #: Enable debug logging.
    debug: bool = False
