"""Module tools for FuzzForge MCP."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from fuzzforge_mcp.dependencies import get_project_path, get_runner, get_settings

if TYPE_CHECKING:
    from fuzzforge_runner import Runner
    from fuzzforge_runner.orchestrator import StepResult


mcp: FastMCP = FastMCP()

# Track running background executions
_background_executions: dict[str, dict[str, Any]] = {}


@mcp.tool
async def list_modules() -> dict[str, Any]:
    """List all available FuzzForge modules.

    Returns information about modules that can be executed,
    including their identifiers, availability status, and metadata
    such as use cases, input requirements, and output artifacts.

    :return: Dictionary with list of available modules and their details.

    """
    try:
        runner: Runner = get_runner()
        settings = get_settings()

        # Use the engine abstraction to list images
        # Default filter matches locally-built fuzzforge-* modules
        modules = runner.list_module_images(filter_prefix="fuzzforge-")

        available_modules = [
            {
                "identifier": module.identifier,
                "image": f"{module.identifier}:{module.version or 'latest'}",
                "available": module.available,
                "description": module.description,
                # New metadata fields from pyproject.toml
                "category": module.category,
                "language": module.language,
                "pipeline_stage": module.pipeline_stage,
                "pipeline_order": module.pipeline_order,
                "dependencies": module.dependencies,
                "continuous_mode": module.continuous_mode,
                "typical_duration": module.typical_duration,
                # AI-discoverable metadata
                "use_cases": module.use_cases,
                "input_requirements": module.input_requirements,
                "output_artifacts": module.output_artifacts,
            }
            for module in modules
        ]

        # Sort by pipeline_order if available
        available_modules.sort(key=lambda m: (m.get("pipeline_order") or 999, m["identifier"]))

        return {
            "modules": available_modules,
            "count": len(available_modules),
            "container_engine": settings.engine.type,
            "registry_url": settings.registry.url,
            "registry_tag": settings.registry.default_tag,
        }

    except Exception as exception:
        message: str = f"Failed to list modules: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def execute_module(
    module_identifier: str,
    configuration: dict[str, Any] | None = None,
    assets_path: str | None = None,
) -> dict[str, Any]:
    """Execute a FuzzForge module in an isolated container.

    This tool runs a module in a sandboxed environment.
    The module receives input assets and produces output results.

    :param module_identifier: The identifier of the module to execute.
    :param configuration: Optional configuration dict to pass to the module.
    :param assets_path: Optional path to input assets. If not provided, uses project assets.
    :return: Execution result including status and results path.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        result: StepResult = await runner.execute_module(
            module_identifier=module_identifier,
            project_path=project_path,
            configuration=configuration,
            assets_path=Path(assets_path) if assets_path else None,
        )

        return {
            "success": result.success,
            "execution_id": result.execution_id,
            "module": result.module_identifier,
            "results_path": str(result.results_path) if result.results_path else None,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat(),
            "error": result.error,
        }

    except Exception as exception:
        message: str = f"Module execution failed: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def start_continuous_module(
    module_identifier: str,
    configuration: dict[str, Any] | None = None,
    assets_path: str | None = None,
) -> dict[str, Any]:
    """Start a module in continuous/background mode.

    The module will run indefinitely until stopped with stop_continuous_module().
    Use get_continuous_status() to check progress and metrics.

    This is useful for long-running modules that should run until
    the user decides to stop them.

    :param module_identifier: The module to run.
    :param configuration: Optional configuration. Set max_duration to 0 for infinite.
    :param assets_path: Optional path to input assets.
    :return: Execution info including session_id for monitoring.

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()
    session_id = str(uuid.uuid4())[:8]

    # Set infinite duration if not specified
    if configuration is None:
        configuration = {}
    if "max_duration" not in configuration:
        configuration["max_duration"] = 0  # 0 = infinite

    try:
        # Determine assets path
        if assets_path:
            actual_assets_path = Path(assets_path)
        else:
            storage = runner.storage
            actual_assets_path = storage.get_project_assets_path(project_path)

        # Use the new non-blocking executor method
        executor = runner._executor
        result = executor.start_module_continuous(
            module_identifier=module_identifier,
            assets_path=actual_assets_path,
            configuration=configuration,
            project_path=project_path,
            execution_id=session_id,
        )

        # Store execution info for tracking
        _background_executions[session_id] = {
            "session_id": session_id,
            "module": module_identifier,
            "configuration": configuration,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "container_id": result["container_id"],
            "input_dir": result["input_dir"],
            "project_path": str(project_path),
        }

        return {
            "success": True,
            "session_id": session_id,
            "module": module_identifier,
            "container_id": result["container_id"],
            "status": "running",
            "message": f"Continuous module started. Use get_continuous_status('{session_id}') to monitor progress.",
        }

    except Exception as exception:
        message: str = f"Failed to start continuous module: {exception}"
        raise ToolError(message) from exception


def _get_continuous_status_impl(session_id: str) -> dict[str, Any]:
    """Internal helper to get continuous session status (non-tool version)."""
    if session_id not in _background_executions:
        raise ToolError(f"Unknown session: {session_id}. Use list_continuous_sessions() to see active sessions.")

    execution = _background_executions[session_id]
    container_id = execution.get("container_id")

    # Initialize metrics
    metrics: dict[str, Any] = {
        "total_executions": 0,
        "total_crashes": 0,
        "exec_per_sec": 0,
        "coverage": 0,
        "current_target": "",
        "latest_events": [],
    }

    # Read stream.jsonl from inside the running container
    if container_id:
        try:
            runner: Runner = get_runner()
            executor = runner._executor

            # Check container status first
            container_status = executor.get_module_status(container_id)
            if container_status != "running":
                execution["status"] = "stopped" if container_status == "exited" else container_status

            # Read stream.jsonl from container
            stream_content = executor.read_module_output(container_id, "/data/output/stream.jsonl")

            if stream_content:
                lines = stream_content.strip().split("\n")
                # Get last 20 events
                recent_lines = lines[-20:] if len(lines) > 20 else lines
                crash_count = 0

                for line in recent_lines:
                    try:
                        event = json.loads(line)
                        metrics["latest_events"].append(event)

                        # Extract metrics from events
                        if event.get("event") == "metrics":
                            metrics["total_executions"] = event.get("executions", 0)
                            metrics["current_target"] = event.get("target", "")
                            metrics["exec_per_sec"] = event.get("exec_per_sec", 0)
                            metrics["coverage"] = event.get("coverage", 0)

                        if event.get("event") == "crash_detected":
                            crash_count += 1

                    except json.JSONDecodeError:
                        continue

                metrics["total_crashes"] = crash_count

        except Exception as e:
            metrics["error"] = str(e)

    # Calculate elapsed time
    started_at = execution.get("started_at", "")
    elapsed_seconds = 0
    if started_at:
        try:
            start_time = datetime.fromisoformat(started_at)
            elapsed_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())
        except Exception:
            pass

    return {
        "session_id": session_id,
        "module": execution.get("module"),
        "status": execution.get("status"),
        "container_id": container_id,
        "started_at": started_at,
        "elapsed_seconds": elapsed_seconds,
        "elapsed_human": f"{elapsed_seconds // 60}m {elapsed_seconds % 60}s",
        "metrics": metrics,
    }


@mcp.tool
async def get_continuous_status(session_id: str) -> dict[str, Any]:
    """Get the current status and metrics of a running continuous session.

    Call this periodically (e.g., every 30 seconds) to get live updates
    on progress and metrics.

    :param session_id: The session ID returned by start_continuous_module().
    :return: Current status, metrics, and any events found.

    """
    return _get_continuous_status_impl(session_id)


@mcp.tool
async def stop_continuous_module(session_id: str) -> dict[str, Any]:
    """Stop a running continuous session.

    This will gracefully stop the module and collect any results.

    :param session_id: The session ID of the session to stop.
    :return: Final status and summary of the session.

    """
    if session_id not in _background_executions:
        raise ToolError(f"Unknown session: {session_id}")

    execution = _background_executions[session_id]
    container_id = execution.get("container_id")
    input_dir = execution.get("input_dir")

    try:
        # Get final metrics before stopping (use helper, not the tool)
        final_metrics = _get_continuous_status_impl(session_id)

        # Stop the container and collect results
        results_path = None
        if container_id:
            runner: Runner = get_runner()
            executor = runner._executor

            try:
                results_path = executor.stop_module_continuous(container_id, input_dir)
            except Exception:
                # Container may have already stopped
                pass

        execution["status"] = "stopped"
        execution["stopped_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "success": True,
            "session_id": session_id,
            "message": "Continuous session stopped",
            "results_path": str(results_path) if results_path else None,
            "final_metrics": final_metrics.get("metrics", {}),
            "elapsed": final_metrics.get("elapsed_human", ""),
        }

    except Exception as exception:
        message: str = f"Failed to stop continuous module: {exception}"
        raise ToolError(message) from exception


@mcp.tool
async def list_continuous_sessions() -> dict[str, Any]:
    """List all active and recent continuous sessions.

    :return: List of continuous sessions with their status.

    """
    sessions = []
    for session_id, execution in _background_executions.items():
        sessions.append({
            "session_id": session_id,
            "module": execution.get("module"),
            "status": execution.get("status"),
            "started_at": execution.get("started_at"),
        })

    return {
        "sessions": sessions,
        "count": len(sessions),
    }

