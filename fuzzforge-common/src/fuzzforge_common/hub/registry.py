"""Hub registry for managing MCP server configurations.

The registry loads server configurations from a JSON file and provides
methods to access and manage them. It does not hardcode any specific
servers or tools - everything is configured by the user.

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fuzzforge_common.hub.models import (
    HubConfig,
    HubServer,
    HubServerConfig,
)

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


class HubRegistry:
    """Registry for MCP hub servers.

    Manages the configuration and state of hub servers.
    Configurations are loaded from a JSON file.

    """

    #: Loaded hub configuration.
    _config: HubConfig

    #: Server instances with discovered tools.
    _servers: dict[str, HubServer]

    #: Path to the configuration file.
    _config_path: Path | None

    def __init__(self, config_path: Path | str | None = None) -> None:
        """Initialize the hub registry.

        :param config_path: Path to hub-servers.json config file.
            If None, starts with empty configuration.

        """
        if config_path is not None:
            self._config_path = Path(config_path)
        else:
            self._config_path = None
        self._servers = {}
        self._config = HubConfig()

        if self._config_path and self._config_path.exists():
            self._load_config(self._config_path)

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from JSON file.

        :param config_path: Path to config file.

        """
        logger = get_logger()
        try:
            with config_path.open() as f:
                data = json.load(f)

            self._config = HubConfig.model_validate(data)

            # Create server instances from config
            for server_config in self._config.servers:
                if server_config.enabled:
                    self._servers[server_config.name] = HubServer(
                        config=server_config,
                    )

            # Load and merge external workflow hints file if specified.
            if self._config.workflow_hints_file:
                hints_path = Path(self._config.workflow_hints_file)
                if not hints_path.is_absolute():
                    hints_path = config_path.parent / hints_path
                if hints_path.exists():
                    try:
                        with hints_path.open() as hf:
                            hints_data = json.load(hf)
                        self._config.workflow_hints.update(hints_data.get("hints", {}))
                        logger.info(
                            "Loaded workflow hints",
                            path=str(hints_path),
                            hints=len(self._config.workflow_hints),
                        )
                    except Exception as hints_err:
                        logger.warning(
                            "Failed to load workflow hints file",
                            path=str(hints_path),
                            error=str(hints_err),
                        )

            logger.info(
                "Loaded hub configuration",
                path=str(config_path),
                servers=len(self._servers),
            )

        except Exception as e:
            logger.error(
                "Failed to load hub configuration",
                path=str(config_path),
                error=str(e),
            )
            raise

    def reload(self) -> None:
        """Reload configuration from file."""
        if self._config_path and self._config_path.exists():
            self._servers.clear()
            self._load_config(self._config_path)

    @property
    def servers(self) -> list[HubServer]:
        """Get all registered servers.

        :returns: List of hub servers.

        """
        return list(self._servers.values())

    @property
    def enabled_servers(self) -> list[HubServer]:
        """Get all enabled servers.

        :returns: List of enabled hub servers.

        """
        return [s for s in self._servers.values() if s.config.enabled]

    def get_server(self, name: str) -> HubServer | None:
        """Get a server by name.

        :param name: Server name.
        :returns: HubServer if found, None otherwise.

        """
        return self._servers.get(name)

    def add_server(self, config: HubServerConfig) -> HubServer:
        """Add a server to the registry.

        :param config: Server configuration.
        :returns: Created HubServer instance.
        :raises ValueError: If server with same name exists.

        """
        if config.name in self._servers:
            msg = f"Server '{config.name}' already exists"
            raise ValueError(msg)

        server = HubServer(config=config)
        self._servers[config.name] = server
        self._config.servers.append(config)

        get_logger().info("Added hub server", name=config.name, type=config.type)
        return server

    def remove_server(self, name: str) -> bool:
        """Remove a server from the registry.

        :param name: Server name.
        :returns: True if removed, False if not found.

        """
        if name not in self._servers:
            return False

        del self._servers[name]
        self._config.servers = [s for s in self._config.servers if s.name != name]

        get_logger().info("Removed hub server", name=name)
        return True

    def save_config(self, path: Path | None = None) -> None:
        """Save current configuration to file.

        :param path: Path to save to. Uses original path if None.

        """
        save_path = path or self._config_path
        if not save_path:
            msg = "No config path specified"
            raise ValueError(msg)

        with save_path.open("w") as f:
            json.dump(
                self._config.model_dump(mode="json"),
                f,
                indent=2,
            )

        get_logger().info("Saved hub configuration", path=str(save_path))

    def update_server_tools(
        self,
        server_name: str,
        tools: list,
        *,
        error: str | None = None,
    ) -> None:
        """Update discovered tools for a server.

        Called by the hub client after tool discovery.

        :param server_name: Server name.
        :param tools: List of HubTool instances.
        :param error: Error message if discovery failed.

        """
        server = self._servers.get(server_name)
        if not server:
            return

        if error:
            server.discovered = False
            server.discovery_error = error
            server.tools = []
        else:
            server.discovered = True
            server.discovery_error = None
            server.tools = tools

    def get_workflow_hint(self, tool_name: str) -> dict | None:
        """Get the workflow hint for a tool by name.

        :param tool_name: Tool name (e.g. ``binwalk_extract``).
        :returns: Hint dict for the ``after:<tool_name>`` key, or None.

        """
        return self._config.workflow_hints.get(f"after:{tool_name}") or None

    def get_all_tools(self) -> list:
        """Get all discovered tools from all servers.

        :returns: Flat list of all HubTool instances.

        """
        tools = []
        for server in self._servers.values():
            if server.discovered:
                tools.extend(server.tools)
        return tools

    def find_tool(self, identifier: str):
        """Find a tool by its full identifier.

        :param identifier: Full identifier (hub:server:tool or server:tool).
        :returns: Tuple of (HubServer, HubTool) if found, (None, None) otherwise.

        """
        # Parse identifier
        parts = identifier.split(":")
        if len(parts) == 3 and parts[0] == "hub":  # noqa: PLR2004
            # hub:server:tool format
            server_name = parts[1]
            tool_name = parts[2]
        elif len(parts) == 2:  # noqa: PLR2004
            # server:tool format
            server_name = parts[0]
            tool_name = parts[1]
        else:
            return None, None

        server = self._servers.get(server_name)
        if not server:
            return None, None

        tool = server.get_tool(tool_name)
        return server, tool
