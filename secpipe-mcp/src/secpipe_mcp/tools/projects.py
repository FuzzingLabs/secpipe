"""Project management tools for SecPipe MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from secpipe_mcp.dependencies import (
    get_active_skill,
    get_project_path,
    get_storage,
    set_active_skill,
    set_current_project_path,
)

mcp: FastMCP = FastMCP()


@mcp.tool
async def init_project(project_path: str | None = None) -> dict[str, Any]:
    """Initialize a new SecPipe project workspace.

    Creates a `.secpipe/` directory for storing configuration and execution results.
    Call this once before using hub tools. The project path is a working directory
    for SecPipe state — it does not need to contain the files you want to analyze.
    Use `set_project_assets` separately to specify the target files.

    :param project_path: Working directory for SecPipe state. Defaults to current directory.
    :return: Project initialization result.

    """
    storage = get_storage()

    try:
        path = Path(project_path) if project_path else get_project_path()

        # Track this as the current active project
        set_current_project_path(path)

        storage_path = storage.init_project(path)

        return {
            "success": True,
            "project_path": str(path),
            "storage_path": str(storage_path),
            "message": f"Project initialized. Storage at {path}/.secpipe/",
        }

    except Exception as exception:
        message: str = f"Failed to initialize project: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def set_project_assets(assets_path: str) -> dict[str, Any]:
    """Set the directory containing target files to analyze.

    Points SecPipe to the directory with your analysis targets
    (firmware images, binaries, source code, etc.). This directory
    is mounted read-only into hub tool containers.

    :param assets_path: Path to the directory containing files to analyze.
    :return: Result including stored assets path.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        stored_path = storage.set_project_assets(
            project_path=project_path,
            assets_path=Path(assets_path),
        )

        return {
            "success": True,
            "project_path": str(project_path),
            "assets_path": str(stored_path),
            "message": f"Assets stored from {assets_path}",
        }

    except Exception as exception:
        message: str = f"Failed to set project assets: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def list_executions() -> dict[str, Any]:
    """List all executions for the current project.

    Returns execution summaries including server, tool, timestamp, and success status.

    :return: List of execution summaries.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        executions = storage.list_executions(project_path)

        return {
            "success": True,
            "project_path": str(project_path),
            "executions": executions,
            "count": len(executions),
        }

    except Exception as exception:
        message: str = f"Failed to list executions: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def get_execution_results(execution_id: str, extract_to: str | None = None) -> dict[str, Any]:
    """Get results for a specific execution.

    :param execution_id: The execution ID to retrieve results for.
    :param extract_to: Optional directory to extract results to.
    :return: Result including path to results archive.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        results_path = storage.get_execution_results(project_path, execution_id)

        if results_path is None:
            return {
                "success": False,
                "execution_id": execution_id,
                "error": "Execution results not found",
            }

        result: dict[str, Any] = {
            "success": True,
            "execution_id": execution_id,
            "results_path": str(results_path),
        }

        # Extract if requested
        if extract_to:
            extracted_path = storage.extract_results(results_path, Path(extract_to))
            result["extracted_path"] = str(extracted_path)

        return result

    except Exception as exception:
        message: str = f"Failed to get execution results: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def list_artifacts(
    source: str | None = None,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    """List all artifacts produced by hub tools in the current project.

    Artifacts are files created by tool executions in /app/output/.
    They are automatically tracked after each execute_hub_tool call.

    :param source: Filter by source server name (e.g. "binwalk-mcp").
    :param artifact_type: Filter by type (e.g. "elf-binary", "json", "text", "archive").
    :return: List of artifacts with path, type, size, and source info.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        artifacts = storage.list_artifacts(
            project_path,
            source=source,
            artifact_type=artifact_type,
        )

        return {
            "success": True,
            "artifacts": artifacts,
            "count": len(artifacts),
        }

    except Exception as exception:
        message: str = f"Failed to list artifacts: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def get_artifact(path: str) -> dict[str, Any]:
    """Get metadata for a specific artifact by its container path.

    :param path: Container path of the artifact (e.g. /app/output/extract_abc123/squashfs-root/usr/sbin/httpd).
    :return: Artifact metadata including path, type, size, source tool, and timestamps.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        artifact = storage.get_artifact(project_path, path)

        if artifact is None:
            return {
                "success": False,
                "path": path,
                "error": "Artifact not found",
            }

        return {
            "success": True,
            "artifact": artifact,
        }

    except Exception as exception:
        message: str = f"Failed to get artifact: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def list_skills() -> dict[str, Any]:
    """List available skill packs.

    Skill packs provide domain-specific pipeline guidance for AI agents.
    They describe analysis methodologies and list the hub servers needed.
    Project-local skills (.secpipe/skills/) override built-in skills.

    :return: List of available skills with name, summary, and server list.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        skills = storage.list_skills(project_path)
        active = get_active_skill()

        return {
            "success": True,
            "skills": skills,
            "count": len(skills),
            "active_skill": active["name"] if active else None,
        }

    except Exception as exception:
        message: str = f"Failed to list skills: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def load_skill(name: str) -> dict[str, Any]:
    """Load a skill pack to guide the current analysis session.

    A skill pack provides a pipeline description and specifies which
    hub servers are relevant. Once loaded, the pipeline description
    is available as context and only the listed servers need discovery.

    :param name: Skill name (e.g. "firmware-analysis").
    :return: Loaded skill with full description and server list.

    """
    storage = get_storage()
    project_path: Path = get_project_path()

    try:
        skill = storage.load_skill(project_path, name)

        if skill is None:
            return {
                "success": False,
                "name": name,
                "error": f"Skill '{name}' not found. Use list_skills to see available skills.",
            }

        set_active_skill(skill)

        return {
            "success": True,
            "name": skill["name"],
            "description": skill["description"],
            "servers": skill["servers"],
            "message": f"Skill '{name}' loaded. Follow the pipeline description above. "
            f"Discover tools from: {', '.join(skill['servers'])}" if skill["servers"] else f"Skill '{name}' loaded.",
        }

    except Exception as exception:
        message: str = f"Failed to load skill: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def unload_skill() -> dict[str, Any]:
    """Unload the currently active skill pack.

    Clears the active pipeline guidance. The agent returns to generic mode.

    :return: Confirmation of unload.

    """
    active = get_active_skill()
    if active is None:
        return {
            "success": True,
            "message": "No skill was loaded.",
        }

    name = active["name"]
    set_active_skill(None)

    return {
        "success": True,
        "message": f"Skill '{name}' unloaded.",
    }
