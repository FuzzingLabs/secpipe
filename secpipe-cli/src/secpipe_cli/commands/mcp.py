"""MCP server configuration commands for SecPipe CLI.

This module provides commands for setting up MCP server connections
with various AI agents (VS Code Copilot, Claude Code, etc.).

"""

from __future__ import annotations

import json
import os
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from typer import Argument, Context, Option, Typer

application: Typer = Typer(
    name="mcp",
    help="MCP server configuration commands.",
)


class AIAgent(StrEnum):
    """Supported AI agents."""

    COPILOT = "copilot"  # GitHub Copilot in VS Code
    CLAUDE_DESKTOP = "claude-desktop"  # Claude Desktop app
    CLAUDE_CODE = "claude-code"  # Claude Code CLI (terminal)


def _get_copilot_mcp_path() -> Path:
    """Get the GitHub Copilot MCP configuration file path.

    GitHub Copilot uses VS Code's mcp.json for MCP servers.

    :returns: Path to the mcp.json file.

    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "mcp.json"
    # Linux
    return Path.home() / ".config" / "Code" / "User" / "mcp.json"


def _get_claude_desktop_mcp_path() -> Path:
    """Get the Claude Desktop MCP configuration file path.

    :returns: Path to the claude_desktop_config.json file.

    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    # Linux
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _get_claude_code_mcp_path(project_path: Path | None = None) -> Path:
    """Get the Claude Code MCP configuration file path.

    Claude Code uses .mcp.json in the project root for project-scoped servers.

    :param project_path: Project directory path. If None, uses current directory.
    :returns: Path to the .mcp.json file.

    """
    if project_path:
        return project_path / ".mcp.json"
    return Path.cwd() / ".mcp.json"


def _get_claude_code_user_mcp_path() -> Path:
    """Get the Claude Code user-scoped MCP configuration file path.

    :returns: Path to ~/.claude.json file.

    """
    return Path.home() / ".claude.json"


def _detect_podman_socket() -> str:
    """Auto-detect the Podman socket path.

    :returns: Path to the Podman socket.

    """
    uid = os.getuid()
    socket_paths = [
        f"/run/user/{uid}/podman/podman.sock",
        "/run/podman/podman.sock",
        "/var/run/podman/podman.sock",
    ]

    for path in socket_paths:
        if Path(path).exists():
            return path

    # Default to user socket
    return f"/run/user/{uid}/podman/podman.sock"


def _detect_docker_socket() -> str:
    """Auto-detect the Docker socket path.

    :returns: Path to the Docker socket.

    """
    socket_paths: list[Path] = [
        Path("/var/run/docker.sock"),
        Path.home() / ".docker" / "run" / "docker.sock",
    ]

    for path in socket_paths:
        if path.exists():
            return str(path)

    return "/var/run/docker.sock"


def _find_secpipe_root() -> Path:
    """Find the SecPipe installation root.

    :returns: Path to secpipe-oss directory.

    """
    # Check environment variable override first
    env_root = os.environ.get("SECPIPE_ROOT")
    if env_root:
        return Path(env_root).resolve()

    # Walk up from cwd to find a secpipe root (hub-config.json is the marker)
    for parent in [Path.cwd(), *Path.cwd().parents]:
        if (parent / "hub-config.json").is_file():
            return parent

    # Fall back to __file__-based search (dev install inside secpipe-oss)
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "secpipe-mcp").is_dir():
            return parent

    return Path.cwd()


def _generate_mcp_config(
    secpipe_root: Path,
    engine_type: str,
    engine_socket: str,
) -> dict[str, Any]:
    """Generate MCP server configuration.

    :param secpipe_root: Path to secpipe-oss installation.
    :param engine_type: Container engine type (podman or docker).
    :param engine_socket: Container engine socket path.
    :returns: MCP configuration dictionary.

    """
    venv_python = secpipe_root / ".venv" / "bin" / "python"

    # Use uv run if no venv, otherwise use venv python directly
    if venv_python.exists():
        command = str(venv_python)
        args = ["-m", "secpipe_mcp"]
    else:
        command = "uv"
        args = ["--directory", str(secpipe_root), "run", "secpipe-mcp"]

    # User-global storage paths for SecPipe containers.
    # Kept under ~/.secpipe so images are built once and shared across
    # all workspaces — regardless of where `secpipe mcp install` is run.
    # Override with SECPIPE_USER_DIR for isolated testing.
    user_dir_env = os.environ.get("SECPIPE_USER_DIR")
    secpipe_home = Path(user_dir_env).resolve() if user_dir_env else Path.home() / ".secpipe"
    graphroot = secpipe_home / "containers" / "storage"
    runroot = secpipe_home / "containers" / "run"

    return {
        "type": "stdio",
        "command": command,
        "args": args,
        "cwd": str(secpipe_root),
        "env": {
            "SECPIPE_ENGINE__TYPE": engine_type,
            "SECPIPE_ENGINE__GRAPHROOT": str(graphroot),
            "SECPIPE_ENGINE__RUNROOT": str(runroot),
            "SECPIPE_HUB__ENABLED": "true",
            "SECPIPE_HUB__CONFIG_PATH": str(secpipe_root / "hub-config.json"),
        },
    }


@application.command(
    help="Show current MCP configuration status.",
    name="status",
)
def status(context: Context) -> None:
    """Show MCP configuration status for all supported agents.

    :param context: Typer context.

    """
    console = Console()

    table = Table(title="MCP Configuration Status")
    table.add_column("Agent", style="cyan")
    table.add_column("Config Path")
    table.add_column("Status")
    table.add_column("SecPipe Configured")

    secpipe_root = _find_secpipe_root()

    agents = [
        ("GitHub Copilot", _get_copilot_mcp_path(), "servers"),
        ("Claude Desktop", _get_claude_desktop_mcp_path(), "mcpServers"),
        ("Claude Code", _get_claude_code_user_mcp_path(), "mcpServers"),
    ]

    for name, config_path, servers_key in agents:
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                servers = config.get(servers_key, {})
                has_secpipe = "secpipe" in servers
                table.add_row(
                    name,
                    str(config_path),
                    "[green]✓ Exists[/green]",
                    "[green]✓ Yes[/green]" if has_secpipe else "[yellow]✗ No[/yellow]",
                )
            except json.JSONDecodeError:
                table.add_row(
                    name,
                    str(config_path),
                    "[red]✗ Invalid JSON[/red]",
                    "[dim]-[/dim]",
                )
        else:
            table.add_row(
                name,
                str(config_path),
                "[dim]Not found[/dim]",
                "[dim]-[/dim]",
            )

    console.print(table)

    # Show detected environment
    console.print()
    console.print("[bold]Detected Environment:[/bold]")
    console.print(f"  SecPipe Root: {_find_secpipe_root()}")
    console.print(f"  Podman Socket:  {_detect_podman_socket()}")
    console.print(f"  Docker Socket:  {_detect_docker_socket()}")


@application.command(
    help="Generate MCP configuration for an AI agent.",
    name="generate",
)
def generate(
    context: Context,
    agent: Annotated[
        AIAgent,
        Argument(
            help="AI agent to generate config for (copilot, claude-desktop, or claude-code).",
        ),
    ],
    engine: Annotated[
        str,
        Option(
            "--engine",
            "-e",
            help="Container engine (docker or podman).",
        ),
    ] = "docker",
) -> None:
    """Generate MCP configuration and print to stdout.

    :param context: Typer context.
    :param agent: Target AI agent.
    :param engine: Container engine type.

    """
    console = Console()
    secpipe_root = _find_secpipe_root()

    # Detect socket
    if engine == "podman":
        socket = _detect_podman_socket()
    else:
        socket = _detect_docker_socket()

    # Generate config
    server_config = _generate_mcp_config(
        secpipe_root=secpipe_root,
        engine_type=engine,
        engine_socket=socket,
    )

    # Format based on agent
    if agent == AIAgent.COPILOT:
        full_config = {"servers": {"secpipe": server_config}}
    else:  # Claude Desktop or Claude Code
        full_config = {"mcpServers": {"secpipe": server_config}}

    config_json = json.dumps(full_config, indent=4)

    console.print(Panel(
        Syntax(config_json, "json", theme="monokai"),
        title=f"MCP Configuration for {agent.value}",
    ))

    # Show where to save it
    if agent == AIAgent.COPILOT:
        config_path = _get_copilot_mcp_path()
    elif agent == AIAgent.CLAUDE_CODE:
        config_path = _get_claude_code_mcp_path(secpipe_root)
    else:  # Claude Desktop
        config_path = _get_claude_desktop_mcp_path()

    console.print()
    console.print(f"[bold]Save to:[/bold] {config_path}")
    console.print()
    console.print("[dim]Or run 'secpipe mcp install' to install automatically.[/dim]")


@application.command(
    help="Install MCP configuration for an AI agent.",
    name="install",
)
def install(
    context: Context,
    agent: Annotated[
        AIAgent,
        Argument(
            help="AI agent to install config for (copilot, claude-desktop, or claude-code).",
        ),
    ],
    engine: Annotated[
        str,
        Option(
            "--engine",
            "-e",
            help="Container engine (docker or podman).",
        ),
    ] = "docker",
    force: Annotated[
        bool,
        Option(
            "--force",
            "-f",
            help="Overwrite existing secpipe configuration.",
        ),
    ] = False,
) -> None:
    """Install MCP configuration for the specified AI agent.

    This will create or update the MCP configuration file, adding the
    secpipe server configuration.

    :param context: Typer context.
    :param agent: Target AI agent.
    :param engine: Container engine type.
    :param force: Overwrite existing configuration.

    """
    console = Console()
    secpipe_root = _find_secpipe_root()

    # Determine config path
    if agent == AIAgent.COPILOT:
        config_path = _get_copilot_mcp_path()
        servers_key = "servers"
    elif agent == AIAgent.CLAUDE_CODE:
        config_path = _get_claude_code_user_mcp_path()
        servers_key = "mcpServers"
    else:  # Claude Desktop
        config_path = _get_claude_desktop_mcp_path()
        servers_key = "mcpServers"

    # Detect socket
    if engine == "podman":
        socket = _detect_podman_socket()
    else:
        socket = _detect_docker_socket()

    # Generate server config
    server_config = _generate_mcp_config(
        secpipe_root=secpipe_root,
        engine_type=engine,
        engine_socket=socket,
    )

    # Load existing config or create new
    if config_path.exists():
        try:
            existing_config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            console.print(f"[red]Error: Invalid JSON in {config_path}[/red]")
            console.print("[dim]Please fix the file manually or delete it.[/dim]")
            raise SystemExit(1)

        # Check if secpipe already exists
        servers = existing_config.get(servers_key, {})
        if "secpipe" in servers and not force:
            console.print("[yellow]SecPipe is already configured.[/yellow]")
            console.print("[dim]Use --force to overwrite existing configuration.[/dim]")
            raise SystemExit(1)

        # Add/update secpipe
        if servers_key not in existing_config:
            existing_config[servers_key] = {}
        existing_config[servers_key]["secpipe"] = server_config

        full_config = existing_config
    else:
        # Create new config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        full_config = {servers_key: {"secpipe": server_config}}

    # Write config
    config_path.write_text(json.dumps(full_config, indent=4))

    console.print(f"[green]✓ Installed SecPipe MCP configuration for {agent.value}[/green]")
    console.print()
    console.print(f"[bold]Configuration file:[/bold] {config_path}")
    console.print()
    console.print("[bold]Settings:[/bold]")
    console.print(f"  Engine:        {engine}")
    console.print(f"  Socket:        {socket}")
    console.print(f"  Hub Config:    {secpipe_root / 'hub-config.json'}")
    console.print()

    console.print("[bold]Next steps:[/bold]")
    if agent == AIAgent.COPILOT:
        console.print("  1. Restart VS Code")
        console.print("  2. Open Copilot Chat and look for SecPipe tools")
    elif agent == AIAgent.CLAUDE_CODE:
        console.print("  1. Run 'claude' from any directory")
        console.print("  2. SecPipe tools will be available")
    else:  # Claude Desktop
        console.print("  1. Restart Claude Desktop")
        console.print("  2. The secpipe MCP server will be available")


@application.command(
    help="Remove MCP configuration for an AI agent.",
    name="uninstall",
)
def uninstall(
    context: Context,
    agent: Annotated[
        AIAgent,
        Argument(
            help="AI agent to remove config from (copilot, claude-desktop, or claude-code).",
        ),
    ],
) -> None:
    """Remove SecPipe MCP configuration from the specified AI agent.

    :param context: Typer context.
    :param agent: Target AI agent.

    """
    console = Console()
    secpipe_root = _find_secpipe_root()

    # Determine config path
    if agent == AIAgent.COPILOT:
        config_path = _get_copilot_mcp_path()
        servers_key = "servers"
    elif agent == AIAgent.CLAUDE_CODE:
        config_path = _get_claude_code_user_mcp_path()
        servers_key = "mcpServers"
    else:  # Claude Desktop
        config_path = _get_claude_desktop_mcp_path()
        servers_key = "mcpServers"

    if not config_path.exists():
        console.print(f"[yellow]Configuration file not found: {config_path}[/yellow]")
        return

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        console.print(f"[red]Error: Invalid JSON in {config_path}[/red]")
        raise SystemExit(1)

    servers = config.get(servers_key, {})
    if "secpipe" not in servers:
        console.print("[yellow]SecPipe is not configured.[/yellow]")
        return

    # Remove secpipe
    del servers["secpipe"]

    # Write back
    config_path.write_text(json.dumps(config, indent=4))

    console.print(f"[green]✓ Removed SecPipe MCP configuration from {agent.value}[/green]")
    console.print()
    console.print("[dim]Restart your AI agent for changes to take effect.[/dim]")
