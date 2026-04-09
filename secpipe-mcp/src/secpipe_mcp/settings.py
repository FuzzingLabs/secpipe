"""SecPipe MCP Server settings.

Standalone settings for the MCP server. Replaces the previous dependency
on secpipe-runner Settings now that the module system has been removed
and SecPipe operates exclusively through MCP hub tools.

All settings can be configured via environment variables with the prefix
``SECPIPE_``. Nested settings use double-underscore as delimiter.

Example:
    ``SECPIPE_ENGINE__TYPE=docker``
    ``SECPIPE_STORAGE__PATH=/data/secpipe``
    ``SECPIPE_HUB__CONFIG_PATH=/path/to/hub-config.json``

"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineType(StrEnum):
    """Supported container engine types."""

    DOCKER = "docker"
    PODMAN = "podman"


class EngineSettings(BaseModel):
    """Container engine configuration."""

    #: Type of container engine to use.
    type: EngineType = EngineType.DOCKER

    #: Path to the container engine socket.
    socket: str = Field(default="")

    #: Custom graph root for Podman storage.
    graphroot: Path = Field(default=Path.home() / ".secpipe" / "containers" / "storage")

    #: Custom run root for Podman runtime state.
    runroot: Path = Field(default=Path.home() / ".secpipe" / "containers" / "run")


class StorageSettings(BaseModel):
    """Storage configuration for local filesystem storage."""

    #: Base path for local storage.
    path: Path = Field(default=Path.home() / ".secpipe" / "storage")


class ProjectSettings(BaseModel):
    """Project configuration."""

    #: Default path for SecPipe projects.
    default_path: Path = Field(default=Path.home() / ".secpipe" / "projects")


class HubSettings(BaseModel):
    """MCP Hub configuration for external tool servers.

    Controls the hub that bridges SecPipe with external MCP servers
    (e.g., mcp-security-hub). AI agents discover and execute tools
    from registered MCP servers.

    Configure via environment variables:
        ``SECPIPE_HUB__ENABLED=true``
        ``SECPIPE_HUB__CONFIG_PATH=/path/to/hub-config.json``
        ``SECPIPE_HUB__TIMEOUT=300``
    """

    #: Whether the MCP hub is enabled.
    enabled: bool = Field(default=True)

    #: Path to the hub configuration JSON file.
    config_path: Path = Field(default=Path.home() / ".secpipe" / "hub-config.json")

    #: Default timeout in seconds for hub tool execution.
    timeout: int = Field(default=300)


class Settings(BaseSettings):
    """SecPipe MCP Server settings.

    Settings can be configured via environment variables with the prefix
    ``SECPIPE_``. Nested settings use double-underscore as delimiter.

    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="SECPIPE_",
    )

    #: Container engine settings.
    engine: EngineSettings = Field(default_factory=EngineSettings)

    #: Storage settings.
    storage: StorageSettings = Field(default_factory=StorageSettings)

    #: Project settings.
    project: ProjectSettings = Field(default_factory=ProjectSettings)

    #: MCP Hub settings.
    hub: HubSettings = Field(default_factory=HubSettings)

    #: Enable debug logging.
    debug: bool = False
