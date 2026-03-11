"""Shared helpers for FuzzForge TUI and CLI.

Provides utility functions for checking AI agent configuration status,
hub server image availability, installing/removing MCP configurations,
and managing linked MCP hub repositories.

"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from fuzzforge_cli.commands.mcp import (
    AIAgent,
    _detect_docker_socket,
    _detect_podman_socket,
    _find_fuzzforge_root,
    _generate_mcp_config,
    _get_claude_code_user_mcp_path,
    _get_claude_desktop_mcp_path,
    _get_copilot_mcp_path,
)

# --- Hub Management Constants ---

FUZZFORGE_DEFAULT_HUB_URL = "git@github.com:FuzzingLabs/mcp-security-hub.git"
FUZZFORGE_DEFAULT_HUB_NAME = "mcp-security-hub"


def get_fuzzforge_user_dir() -> Path:
    """Return the user-global ``~/.fuzzforge/`` directory.

    Stores data that is shared across all workspaces: cloned hub
    repositories, the hub registry, container storage (graphroot/runroot),
    and the hub workspace volume.

    Override with the ``FUZZFORGE_USER_DIR`` environment variable to
    redirect all user-global data to a custom path — useful for testing
    a fresh install without touching the real ``~/.fuzzforge/``.

    :return: ``Path.home() / ".fuzzforge"`` or ``$FUZZFORGE_USER_DIR``

    """
    env_dir = os.environ.get("FUZZFORGE_USER_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return Path.home() / ".fuzzforge"


def get_fuzzforge_dir() -> Path:
    """Return the project-local ``.fuzzforge/`` directory.

    Stores data that is specific to the current workspace: fuzzing
    results and project artifacts.  Similar to how ``.git/`` scopes
    version-control data to a single project.

    :return: ``Path.cwd() / ".fuzzforge"``

    """
    return Path.cwd() / ".fuzzforge"

# Categories that typically need NET_RAW capability for network access
_NET_RAW_CATEGORIES = {"reconnaissance", "web-security"}

# Directories to skip when scanning a hub for MCP tool Dockerfiles
_SCAN_SKIP_DIRS = {
    ".git",
    ".github",
    "scripts",
    "tests",
    "examples",
    "meta",
    "__pycache__",
    "node_modules",
    ".venv",
}


def get_agent_configs() -> list[tuple[str, AIAgent, Path, str]]:
    """Return agent display configs with resolved paths.

    Each tuple contains:
    - Display name
    - AIAgent enum value
    - Config file path
    - Servers JSON key

    :return: List of agent configuration tuples.

    """
    return [
        ("GitHub Copilot", AIAgent.COPILOT, _get_copilot_mcp_path(), "servers"),
        ("Claude Desktop", AIAgent.CLAUDE_DESKTOP, _get_claude_desktop_mcp_path(), "mcpServers"),
        ("Claude Code", AIAgent.CLAUDE_CODE, _get_claude_code_user_mcp_path(), "mcpServers"),
    ]


def check_agent_status(config_path: Path, servers_key: str) -> tuple[bool, str]:
    """Check whether an AI agent has FuzzForge configured.

    :param config_path: Path to the agent's MCP config file.
    :param servers_key: JSON key for the servers dict (e.g. "servers" or "mcpServers").
    :return: Tuple of (is_linked, status_description).

    """
    if not config_path.exists():
        return False, "Not configured"
    try:
        config = json.loads(config_path.read_text())
        servers = config.get(servers_key, {})
        if "fuzzforge" in servers:
            return True, "Linked"
        return False, "Config exists, not linked"
    except json.JSONDecodeError:
        return False, "Invalid config file"


def check_hub_image(image: str) -> tuple[bool, str]:
    """Check whether a container image exists locally.

    Respects the ``FUZZFORGE_ENGINE__TYPE`` environment variable so that
    Podman users see the correct build status instead of always "Not built".

    :param image: Image name (e.g. "semgrep-mcp:latest").
    :return: Tuple of (is_ready, status_description).

    """
    engine = os.environ.get("FUZZFORGE_ENGINE__TYPE", "docker").lower()
    cmd = "podman" if engine == "podman" else "docker"
    try:
        result = subprocess.run(
            [cmd, "image", "inspect", image],
            check=False, capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "Ready"
        return False, "Not built"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, f"{cmd} not found"


def load_hub_config(fuzzforge_root: Path) -> dict[str, Any]:
    """Load hub-config.json from the FuzzForge root.

    :param fuzzforge_root: Path to fuzzforge-oss directory.
    :return: Parsed hub configuration dict, empty dict on error.

    """
    config_path = fuzzforge_root / "hub-config.json"
    if not config_path.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(config_path.read_text())
        return data
    except json.JSONDecodeError:
        return {}


def find_fuzzforge_root() -> Path:
    """Find the FuzzForge installation root directory.

    :return: Path to the fuzzforge-oss directory.

    """
    return _find_fuzzforge_root()


def install_agent_config(agent: AIAgent, engine: str, force: bool = False) -> str:
    """Install FuzzForge MCP configuration for an AI agent.

    :param agent: Target AI agent.
    :param engine: Container engine type ("docker" or "podman").
    :param force: Overwrite existing configuration.
    :return: Result message string.

    """
    fuzzforge_root = _find_fuzzforge_root()

    if agent == AIAgent.COPILOT:
        config_path = _get_copilot_mcp_path()
        servers_key = "servers"
    elif agent == AIAgent.CLAUDE_CODE:
        config_path = _get_claude_code_user_mcp_path()
        servers_key = "mcpServers"
    else:
        config_path = _get_claude_desktop_mcp_path()
        servers_key = "mcpServers"

    socket = _detect_docker_socket() if engine == "docker" else _detect_podman_socket()

    server_config = _generate_mcp_config(
        fuzzforge_root=fuzzforge_root,
        engine_type=engine,
        engine_socket=socket,
    )

    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            return f"Error: Invalid JSON in {config_path}"

        servers = existing.get(servers_key, {})
        if "fuzzforge" in servers and not force:
            return "Already configured (use force to overwrite)"

        if servers_key not in existing:
            existing[servers_key] = {}
        existing[servers_key]["fuzzforge"] = server_config
        full_config = existing
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        full_config = {servers_key: {"fuzzforge": server_config}}

    config_path.write_text(json.dumps(full_config, indent=4))
    return f"Installed FuzzForge for {agent.value}"


def uninstall_agent_config(agent: AIAgent) -> str:
    """Remove FuzzForge MCP configuration from an AI agent.

    :param agent: Target AI agent.
    :return: Result message string.

    """
    if agent == AIAgent.COPILOT:
        config_path = _get_copilot_mcp_path()
        servers_key = "servers"
    elif agent == AIAgent.CLAUDE_CODE:
        config_path = _get_claude_code_user_mcp_path()
        servers_key = "mcpServers"
    else:
        config_path = _get_claude_desktop_mcp_path()
        servers_key = "mcpServers"

    if not config_path.exists():
        return "Configuration file not found"

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return "Error: Invalid JSON in config file"

    servers = config.get(servers_key, {})
    if "fuzzforge" not in servers:
        return "FuzzForge is not configured for this agent"

    del servers["fuzzforge"]
    config_path.write_text(json.dumps(config, indent=4))
    return f"Removed FuzzForge from {agent.value}"


# ---------------------------------------------------------------------------
# Hub Management
# ---------------------------------------------------------------------------


def get_hubs_registry_path() -> Path:
    """Return path to the hubs registry file (``~/.fuzzforge/hubs.json``).

    Stored in the user-global directory so the registry is shared across
    all workspaces.

    :return: Path to the registry JSON file.

    """
    return get_fuzzforge_user_dir() / "hubs.json"


def get_default_hubs_dir() -> Path:
    """Return default directory for cloned hubs (``~/.fuzzforge/hubs/``).

    Stored in the user-global directory so hubs are cloned once and
    reused in every workspace.

    :return: Path to the default hubs directory.

    """
    return get_fuzzforge_user_dir() / "hubs"


def _discover_hub_dirs() -> list[Path]:
    """Scan known hub directories for cloned repos.

    Checks both the current global location (``~/.fuzzforge/hubs/``) and the
    legacy workspace-local location (``<cwd>/.fuzzforge/hubs/``) so that hubs
    cloned before the global-dir migration are still found.

    :return: List of hub directory paths (each is a direct child with a ``.git``
        sub-directory).

    """
    candidates: list[Path] = []
    for base in (get_fuzzforge_user_dir() / "hubs", get_fuzzforge_dir() / "hubs"):
        if base.is_dir():
            candidates.extend(
                entry for entry in base.iterdir()
                if entry.is_dir() and (entry / ".git").is_dir()
            )
    return candidates


def load_hubs_registry() -> dict[str, Any]:
    """Load the hubs registry from disk.

    If the registry file does not exist, auto-recovers it by scanning known hub
    directories and rebuilding entries for any discovered hubs.  This handles
    the migration from the old workspace-local ``<cwd>/.fuzzforge/hubs.json``
    path to the global ``~/.fuzzforge/hubs.json`` path, as well as any case
    where the registry was lost.

    :return: Registry dict with ``hubs`` key containing a list of hub entries.

    """
    path = get_hubs_registry_path()
    if path.exists():
        try:
            data: dict[str, Any] = json.loads(path.read_text())
            return data
        except (json.JSONDecodeError, OSError):
            pass

    # Registry missing — attempt to rebuild from discovered hub directories.
    discovered = _discover_hub_dirs()
    if not discovered:
        return {"hubs": []}

    hubs: list[dict[str, Any]] = []
    for hub_dir in discovered:
        name = hub_dir.name
        # Try to read the git remote URL
        git_url: str = ""
        try:
            import subprocess as _sp
            r = _sp.run(
                ["git", "-C", str(hub_dir), "remote", "get-url", "origin"],
                check=False, capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                git_url = r.stdout.strip()
        except Exception:  # noqa: S110 - git URL is optional, failure is acceptable
            pass
        hubs.append({
            "name": name,
            "path": str(hub_dir),
            "git_url": git_url,
            "is_default": name == FUZZFORGE_DEFAULT_HUB_NAME,
        })

    registry: dict[str, Any] = {"hubs": hubs}
    # Persist so we don't re-scan on every load
    with contextlib.suppress(OSError):
        save_hubs_registry(registry)
    return registry


def save_hubs_registry(registry: dict[str, Any]) -> None:
    """Save the hubs registry to disk.

    :param registry: Registry dict to persist.

    """
    path = get_hubs_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2))


def scan_hub_for_servers(hub_path: Path) -> list[dict[str, Any]]:
    """Scan a hub directory for MCP tool Dockerfiles.

    Looks for the ``category/tool-name/Dockerfile`` pattern and generates
    a server configuration entry for each discovered tool.

    :param hub_path: Root directory of the hub repository.
    :return: Sorted list of server configuration dicts.

    """
    servers: list[dict[str, Any]] = []

    if not hub_path.is_dir():
        return servers

    for dockerfile in sorted(hub_path.rglob("Dockerfile")):
        rel = dockerfile.relative_to(hub_path)
        parts = rel.parts

        # Expected layout: category/tool-name/Dockerfile (exactly 3 parts)
        if len(parts) != 3:
            continue

        category, tool_name, _ = parts

        if category in _SCAN_SKIP_DIRS:
            continue

        capabilities: list[str] = []
        if category in _NET_RAW_CATEGORIES:
            capabilities = ["NET_RAW"]

        servers.append(
            {
                "name": tool_name,
                "description": f"{tool_name} — {category}",
                "type": "docker",
                "image": f"{tool_name}:latest",
                "category": category,
                "capabilities": capabilities,
                "volumes": [f"{get_fuzzforge_user_dir()}/hub/workspace:/data"],
                "enabled": True,
            }
        )

    return servers


def link_hub(
    name: str,
    path: str | Path,
    git_url: str | None = None,
    is_default: bool = False,
) -> str:
    """Link a hub directory and add its servers to hub-config.json.

    :param name: Display name for the hub.
    :param path: Local directory path containing the hub.
    :param git_url: Optional git remote URL (for tracking).
    :param is_default: Whether this is the default FuzzingLabs hub.
    :return: Result message string.

    """
    hub_path = Path(path).resolve()

    if not hub_path.is_dir():
        return f"Error: directory not found: {hub_path}"

    # Update registry
    registry = load_hubs_registry()
    hubs = registry.get("hubs", [])

    # Remove existing entry with same name
    hubs = [h for h in hubs if h.get("name") != name]

    hubs.append(
        {
            "name": name,
            "path": str(hub_path),
            "git_url": git_url,
            "is_default": is_default,
        }
    )

    registry["hubs"] = hubs
    save_hubs_registry(registry)

    # Scan and update hub-config.json
    scanned = scan_hub_for_servers(hub_path)
    if not scanned:
        return f"Linked '{name}' (0 servers found)"

    try:
        added = _merge_servers_into_hub_config(name, scanned)
    except Exception as exc:
        return f"Linked '{name}' but config update failed: {exc}"

    return f"Linked '{name}' — {added} new servers added ({len(scanned)} scanned)"


def unlink_hub(name: str) -> str:
    """Unlink a hub and remove its servers from hub-config.json.

    :param name: Name of the hub to unlink.
    :return: Result message string.

    """
    registry = load_hubs_registry()
    hubs = registry.get("hubs", [])

    if not any(h.get("name") == name for h in hubs):
        return f"Hub '{name}' is not linked"

    hubs = [h for h in hubs if h.get("name") != name]
    registry["hubs"] = hubs
    save_hubs_registry(registry)

    try:
        removed = _remove_hub_servers_from_config(name)
    except Exception:
        removed = 0

    return f"Unlinked '{name}' — {removed} server(s) removed"


def clone_hub(
    git_url: str,
    dest: Path | None = None,
    name: str | None = None,
) -> tuple[bool, str, Path | None]:
    """Clone a git hub repository.

    If the destination already exists and is a git repo, pulls instead.

    :param git_url: Git remote URL to clone.
    :param dest: Destination directory (auto-derived from URL if *None*).
    :param name: Hub name (auto-derived from URL if *None*).
    :return: Tuple of ``(success, message, clone_path)``.

    """
    if name is None:
        name = git_url.rstrip("/").split("/")[-1]
        name = name.removesuffix(".git")

    if dest is None:
        dest = get_default_hubs_dir() / name

    if dest.exists():
        if (dest / ".git").is_dir():
            try:
                result = subprocess.run(
                    ["git", "-C", str(dest), "pull"],
                    check=False, capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    return True, f"Updated existing clone at {dest}", dest
                return False, f"Git pull failed: {result.stderr.strip()}", None
            except subprocess.TimeoutExpired:
                return False, "Git pull timed out", None
            except FileNotFoundError:
                return False, "Git not found", None
        return False, f"Directory already exists (not a git repo): {dest}", None

    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["git", "clone", git_url, str(dest)],
            check=False, capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, f"Cloned to {dest}", dest
        return False, f"Git clone failed: {result.stderr.strip()}", None
    except subprocess.TimeoutExpired:
        return False, "Git clone timed out (5 min limit)", None
    except FileNotFoundError:
        return False, "Git not found on PATH", None


def _merge_servers_into_hub_config(
    hub_name: str,
    servers: list[dict[str, Any]],
) -> int:
    """Merge scanned servers into hub-config.json.

    Only adds servers whose name does not already exist in the config.
    New entries are tagged with ``source_hub`` for later removal.

    :param hub_name: Name of the source hub (used for tagging).
    :param servers: List of server dicts from :func:`scan_hub_for_servers`.
    :return: Number of newly added servers.

    """
    fuzzforge_root = find_fuzzforge_root()
    config_path = fuzzforge_root / "hub-config.json"

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            config = {"servers": [], "default_timeout": 300, "cache_tools": True}
    else:
        config = {"servers": [], "default_timeout": 300, "cache_tools": True}

    existing = config.get("servers", [])
    existing_names = {s.get("name") for s in existing}

    added = 0
    for server in servers:
        if server["name"] not in existing_names:
            server["source_hub"] = hub_name
            existing.append(server)
            existing_names.add(server["name"])
            added += 1

    config["servers"] = existing
    config_path.write_text(json.dumps(config, indent=2))
    return added


def _remove_hub_servers_from_config(hub_name: str) -> int:
    """Remove servers belonging to a hub from hub-config.json.

    Only removes servers tagged with the given ``source_hub`` value.
    Manually-added servers (without a tag) are preserved.

    :param hub_name: Name of the hub whose servers should be removed.
    :return: Number of servers removed.

    """
    fuzzforge_root = find_fuzzforge_root()
    config_path = fuzzforge_root / "hub-config.json"

    if not config_path.exists():
        return 0

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return 0

    existing = config.get("servers", [])
    before = len(existing)
    config["servers"] = [s for s in existing if s.get("source_hub") != hub_name]
    after = len(config["servers"])

    config_path.write_text(json.dumps(config, indent=2))
    return before - after


def find_dockerfile_for_server(server_name: str, hub_name: str) -> Path | None:
    """Find the Dockerfile for a hub server tool.

    Looks up the hub path from the registry, then scans for
    ``category/<server_name>/Dockerfile``.

    :param server_name: Tool name (e.g. ``"nmap-mcp"``).
    :param hub_name: Hub name as stored in the registry.
    :return: Absolute path to the Dockerfile, or ``None`` if not found.

    """
    registry = load_hubs_registry()
    hub_entry = next(
        (h for h in registry.get("hubs", []) if h.get("name") == hub_name),
        None,
    )
    if not hub_entry:
        return None

    hub_path = Path(hub_entry["path"])
    for dockerfile in hub_path.rglob("Dockerfile"):
        rel = dockerfile.relative_to(hub_path)
        parts = rel.parts
        if len(parts) == 3 and parts[1] == server_name:
            return dockerfile

    return None


def build_image(
    image: str,
    dockerfile: Path,
    *,
    engine: str | None = None,
) -> subprocess.Popen[str]:
    """Start a non-blocking ``docker/podman build`` subprocess.

    Returns the running :class:`subprocess.Popen` object so the caller
    can stream ``stdout`` / ``stderr`` lines incrementally.

    :param image: Image tag (e.g. ``"nmap-mcp:latest"``).
    :param dockerfile: Path to the ``Dockerfile``.
    :param engine: ``"docker"`` or ``"podman"`` (auto-detected if ``None``).
    :return: Running subprocess with merged stdout+stderr.

    """
    if engine is None:
        engine = os.environ.get("FUZZFORGE_ENGINE__TYPE", "docker").lower()
        engine = "podman" if engine == "podman" else "docker"

    context_dir = str(dockerfile.parent)
    return subprocess.Popen(
        [engine, "build", "-t", image, context_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
