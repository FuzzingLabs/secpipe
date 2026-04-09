"""Data models for SecPipe Hub.

This module defines the Pydantic models used to represent MCP servers
and their tools in the hub registry.

"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HubServerType(str, Enum):
    """Type of MCP server connection."""

    #: Run as Docker container with stdio transport.
    DOCKER = "docker"
    #: Run as local command/process with stdio transport.
    COMMAND = "command"
    #: Connect via Server-Sent Events (HTTP).
    SSE = "sse"


class HubServerConfig(BaseModel):
    """Configuration for an MCP server in the hub.

    This defines how to connect to an MCP server, not what tools it provides.
    Tools are discovered dynamically at runtime.

    """

    #: Unique identifier for this server (e.g., "nmap", "nuclei").
    name: str = Field(description="Unique server identifier")

    #: Human-readable description of the server.
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )

    #: Type of connection to use.
    type: HubServerType = Field(description="Connection type")

    #: Docker image name (for type=docker).
    image: str | None = Field(
        default=None,
        description="Docker image name (for docker type)",
    )

    #: Command to run (for type=command).
    command: list[str] | None = Field(
        default=None,
        description="Command and args (for command type)",
    )

    #: URL endpoint (for type=sse).
    url: str | None = Field(
        default=None,
        description="SSE endpoint URL (for sse type)",
    )

    #: Environment variables to pass to the server.
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )

    #: Docker capabilities to add (e.g., ["NET_RAW"] for nmap).
    capabilities: list[str] = Field(
        default_factory=list,
        description="Docker capabilities to add",
    )

    #: Volume mounts for Docker (e.g., ["/host/path:/container/path:ro"]).
    volumes: list[str] = Field(
        default_factory=list,
        description="Docker volume mounts",
    )

    #: Whether this server is enabled.
    enabled: bool = Field(
        default=True,
        description="Whether server is enabled",
    )

    #: Category for grouping (e.g., "reconnaissance", "web-security").
    category: str | None = Field(
        default=None,
        description="Category for grouping servers",
    )

    #: Per-server timeout override in seconds (None = use default_timeout).
    timeout: int | None = Field(
        default=None,
        description="Per-server execution timeout override in seconds",
    )

    #: Whether to use persistent container mode (keep container running between calls).
    persistent: bool = Field(
        default=False,
        description="Keep container running between tool calls for stateful interactions",
    )


class HubToolParameter(BaseModel):
    """A parameter for an MCP tool.

    Parsed from the tool's JSON Schema inputSchema.

    """

    #: Parameter name.
    name: str

    #: Parameter type (string, integer, boolean, array, object).
    type: str

    #: Human-readable description.
    description: str | None = None

    #: Whether this parameter is required.
    required: bool = False

    #: Default value if any.
    default: Any = None

    #: Enum values if constrained.
    enum: list[Any] | None = None


class HubTool(BaseModel):
    """An MCP tool discovered from a hub server.

    This is populated by calling `list_tools()` on the MCP server.

    """

    #: Tool name as defined by the MCP server.
    name: str = Field(description="Tool name from MCP server")

    #: Human-readable description.
    description: str | None = Field(
        default=None,
        description="Tool description",
    )

    #: Name of the hub server this tool belongs to.
    server_name: str = Field(description="Parent server name")

    #: Parsed parameters from inputSchema.
    parameters: list[HubToolParameter] = Field(
        default_factory=list,
        description="Tool parameters",
    )

    #: Raw JSON Schema for the tool input.
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw JSON Schema from MCP",
    )

    @property
    def identifier(self) -> str:
        """Get the full tool identifier (hub:server:tool)."""
        return f"hub:{self.server_name}:{self.name}"

    @classmethod
    def from_mcp_tool(
        cls,
        server_name: str,
        name: str,
        description: str | None,
        input_schema: dict[str, Any],
    ) -> HubTool:
        """Create a HubTool from MCP tool metadata.

        :param server_name: Name of the parent hub server.
        :param name: Tool name.
        :param description: Tool description.
        :param input_schema: JSON Schema for tool input.
        :returns: HubTool instance.

        """
        parameters = cls._parse_parameters(input_schema)
        return cls(
            name=name,
            description=description,
            server_name=server_name,
            parameters=parameters,
            input_schema=input_schema,
        )

    @staticmethod
    def _parse_parameters(schema: dict[str, Any]) -> list[HubToolParameter]:
        """Parse parameters from JSON Schema.

        :param schema: JSON Schema dict.
        :returns: List of parsed parameters.

        """
        parameters: list[HubToolParameter] = []
        properties = schema.get("properties", {})
        required_params = set(schema.get("required", []))

        for name, prop in properties.items():
            param = HubToolParameter(
                name=name,
                type=prop.get("type", "string"),
                description=prop.get("description"),
                required=name in required_params,
                default=prop.get("default"),
                enum=prop.get("enum"),
            )
            parameters.append(param)

        return parameters


class HubServer(BaseModel):
    """A hub server with its discovered tools.

    Combines configuration with dynamically discovered tools.

    """

    #: Server configuration.
    config: HubServerConfig

    #: Tools discovered from the server (populated at runtime).
    tools: list[HubTool] = Field(
        default_factory=list,
        description="Discovered tools",
    )

    #: Whether tools have been discovered.
    discovered: bool = Field(
        default=False,
        description="Whether tools have been discovered",
    )

    #: Error message if discovery failed.
    discovery_error: str | None = Field(
        default=None,
        description="Error message if discovery failed",
    )

    @property
    def name(self) -> str:
        """Get server name."""
        return self.config.name

    @property
    def identifier(self) -> str:
        """Get server identifier for module listing."""
        return f"hub:{self.config.name}"

    def get_tool(self, tool_name: str) -> HubTool | None:
        """Get a tool by name.

        :param tool_name: Name of the tool.
        :returns: HubTool if found, None otherwise.

        """
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None


class HubConfig(BaseModel):
    """Configuration for the entire hub.

    Loaded from hub-servers.json or similar config file.

    """

    #: List of configured servers.
    servers: list[HubServerConfig] = Field(
        default_factory=list,
        description="Configured MCP servers",
    )

    #: Default timeout for tool execution (seconds).
    default_timeout: int = Field(
        default=300,
        description="Default execution timeout",
    )

    #: Whether to cache discovered tools.
    cache_tools: bool = Field(
        default=True,
        description="Cache discovered tools",
    )

    #: Workflow hints indexed by "after:<tool_name>" keys.
    #: Loaded inline or merged from workflow_hints_file.
    workflow_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow hints indexed by 'after:<tool_name>'",
    )

    #: Optional path to an external workflow-hints.json file.
    #: Relative paths are resolved relative to the hub-config.json location.
    workflow_hints_file: str | None = Field(
        default=None,
        description="Path to an external workflow-hints.json to load and merge",
    )
