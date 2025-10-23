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

import asyncio
import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from typing import Any, Dict, Optional, List

import uvicorn
from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.routing import Mount

from fastmcp.server.http import create_sse_app

from src.temporal.manager import TemporalManager
from src.core.setup import setup_result_storage, validate_infrastructure
from src.api import workflows, runs, fuzzing, system

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

temporal_mgr = TemporalManager()


class TemporalBootstrapState:
    """Tracks Temporal initialization progress for API and MCP consumers."""

    def __init__(self) -> None:
        self.ready: bool = False
        self.status: str = "not_started"
        self.last_error: Optional[str] = None
        self.task_running: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "last_error": self.last_error,
            "task_running": self.task_running,
        }


temporal_bootstrap_state = TemporalBootstrapState()

# Configure retry strategy for bootstrapping Temporal + infrastructure
STARTUP_RETRY_SECONDS = max(1, int(os.getenv("FUZZFORGE_STARTUP_RETRY_SECONDS", "5")))
STARTUP_RETRY_MAX_SECONDS = max(
    STARTUP_RETRY_SECONDS,
    int(os.getenv("FUZZFORGE_STARTUP_RETRY_MAX_SECONDS", "60")),
)

temporal_bootstrap_task: Optional[asyncio.Task] = None

# ---------------------------------------------------------------------------
# FastAPI application (REST API)
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FuzzForge API",
    description="Security testing workflow orchestration API with fuzzing support",
    version="0.6.0",
)

app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(fuzzing.router)
app.include_router(system.router)


def get_temporal_status() -> Dict[str, Any]:
    """Return a snapshot of Temporal bootstrap state for diagnostics."""
    status = temporal_bootstrap_state.as_dict()
    status["workflows_loaded"] = len(temporal_mgr.workflows)
    status["bootstrap_task_running"] = (
        temporal_bootstrap_task is not None and not temporal_bootstrap_task.done()
    )
    return status


def _temporal_not_ready_status() -> Optional[Dict[str, Any]]:
    """Return status details if Temporal is not ready yet."""
    status = get_temporal_status()
    if status.get("ready"):
        return None
    return status


@app.get("/")
async def root() -> Dict[str, Any]:
    status = get_temporal_status()
    return {
        "name": "FuzzForge API",
        "version": "0.6.0",
        "status": "ready" if status.get("ready") else "initializing",
        "workflows_loaded": status.get("workflows_loaded", 0),
        "temporal": status,
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    status = get_temporal_status()
    health_status = "healthy" if status.get("ready") else "initializing"
    return {"status": health_status}


# Map FastAPI OpenAPI operationIds to readable MCP tool names
FASTAPI_MCP_NAME_OVERRIDES: Dict[str, str] = {
    "list_workflows_workflows__get": "api_list_workflows",
    "get_metadata_schema_workflows_metadata_schema_get": "api_get_metadata_schema",
    "get_workflow_metadata_workflows__workflow_name__metadata_get": "api_get_workflow_metadata",
    "submit_workflow_workflows__workflow_name__submit_post": "api_submit_workflow",
    "get_workflow_parameters_workflows__workflow_name__parameters_get": "api_get_workflow_parameters",
    "get_run_status_runs__run_id__status_get": "api_get_run_status",
    "get_run_findings_runs__run_id__findings_get": "api_get_run_findings",
    "get_workflow_findings_runs__workflow_name__findings__run_id__get": "api_get_workflow_findings",
    "get_fuzzing_stats_fuzzing__run_id__stats_get": "api_get_fuzzing_stats",
    "update_fuzzing_stats_fuzzing__run_id__stats_post": "api_update_fuzzing_stats",
    "get_crash_reports_fuzzing__run_id__crashes_get": "api_get_crash_reports",
    "report_crash_fuzzing__run_id__crash_post": "api_report_crash",
    "stream_fuzzing_updates_fuzzing__run_id__stream_get": "api_stream_fuzzing_updates",
    "cleanup_fuzzing_run_fuzzing__run_id__delete": "api_cleanup_fuzzing_run",
    "root__get": "api_root",
    "health_health_get": "api_health",
}


# Create an MCP adapter exposing all FastAPI endpoints via OpenAPI parsing
FASTAPI_MCP_ADAPTER = FastMCP.from_fastapi(
    app,
    name="FuzzForge FastAPI",
    mcp_names=FASTAPI_MCP_NAME_OVERRIDES,
)
_fastapi_mcp_imported = False


# ---------------------------------------------------------------------------
# FastMCP server (runs on dedicated port outside FastAPI)
# ---------------------------------------------------------------------------

mcp = FastMCP(name="FuzzForge MCP")


async def _bootstrap_temporal_with_retries() -> None:
    """Initialize Temporal infrastructure with exponential backoff retries."""

    attempt = 0

    while True:
        attempt += 1
        temporal_bootstrap_state.task_running = True
        temporal_bootstrap_state.status = "starting"
        temporal_bootstrap_state.ready = False
        temporal_bootstrap_state.last_error = None

        try:
            logger.info("Bootstrapping Temporal infrastructure...")
            await validate_infrastructure()
            await setup_result_storage()
            await temporal_mgr.initialize()

            temporal_bootstrap_state.ready = True
            temporal_bootstrap_state.status = "ready"
            temporal_bootstrap_state.task_running = False
            logger.info("Temporal infrastructure ready")
            return

        except asyncio.CancelledError:
            temporal_bootstrap_state.status = "cancelled"
            temporal_bootstrap_state.task_running = False
            logger.info("Temporal bootstrap task cancelled")
            raise

        except Exception as exc:  # pragma: no cover - defensive logging on infra startup
            logger.exception("Temporal bootstrap failed")
            temporal_bootstrap_state.ready = False
            temporal_bootstrap_state.status = "error"
            temporal_bootstrap_state.last_error = str(exc)

            # Ensure partial initialization does not leave stale state behind
            temporal_mgr.workflows.clear()

            wait_time = min(
                STARTUP_RETRY_SECONDS * (2 ** (attempt - 1)),
                STARTUP_RETRY_MAX_SECONDS,
            )
            logger.info("Retrying Temporal bootstrap in %s second(s)", wait_time)

            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                temporal_bootstrap_state.status = "cancelled"
                temporal_bootstrap_state.task_running = False
                raise


def _lookup_workflow(workflow_name: str):
    info = temporal_mgr.workflows.get(workflow_name)
    if not info:
        return None
    metadata = info.metadata
    defaults = metadata.get("default_parameters", {})
    default_target_path = metadata.get("default_target_path") or defaults.get("target_path")
    return {
        "name": workflow_name,
        "version": metadata.get("version", "0.6.0"),
        "description": metadata.get("description", ""),
        "author": metadata.get("author"),
        "tags": metadata.get("tags", []),
        "parameters": metadata.get("parameters", {}),
        "default_parameters": metadata.get("default_parameters", {}),
        "required_modules": metadata.get("required_modules", []),
        "default_target_path": default_target_path
    }


@mcp.tool
async def list_workflows_mcp() -> Dict[str, Any]:
    """List all discovered workflows and their metadata summary."""
    not_ready = _temporal_not_ready_status()
    if not_ready:
        return {
            "workflows": [],
            "temporal": not_ready,
            "message": "Temporal infrastructure is still initializing",
        }

    workflows_summary = []
    for name, info in temporal_mgr.workflows.items():
        metadata = info.metadata
        defaults = metadata.get("default_parameters", {})
        workflows_summary.append({
            "name": name,
            "version": metadata.get("version", "0.6.0"),
            "description": metadata.get("description", ""),
            "author": metadata.get("author"),
            "tags": metadata.get("tags", []),
            "default_target_path": metadata.get("default_target_path")
            or defaults.get("target_path")
        })
    return {"workflows": workflows_summary, "temporal": get_temporal_status()}


@mcp.tool
async def get_workflow_metadata_mcp(workflow_name: str) -> Dict[str, Any]:
    """Fetch detailed metadata for a workflow."""
    not_ready = _temporal_not_ready_status()
    if not_ready:
        return {
            "error": "Temporal infrastructure not ready",
            "temporal": not_ready,
        }

    data = _lookup_workflow(workflow_name)
    if not data:
        return {"error": f"Workflow not found: {workflow_name}"}
    return data


@mcp.tool
async def get_workflow_parameters_mcp(workflow_name: str) -> Dict[str, Any]:
    """Return the parameter schema and defaults for a workflow."""
    not_ready = _temporal_not_ready_status()
    if not_ready:
        return {
            "error": "Temporal infrastructure not ready",
            "temporal": not_ready,
        }

    data = _lookup_workflow(workflow_name)
    if not data:
        return {"error": f"Workflow not found: {workflow_name}"}
    return {
        "parameters": data.get("parameters", {}),
        "defaults": data.get("default_parameters", {}),
    }


@mcp.tool
async def get_workflow_metadata_schema_mcp() -> Dict[str, Any]:
    """Return the JSON schema describing workflow metadata files."""
    from src.temporal.discovery import WorkflowDiscovery
    return WorkflowDiscovery.get_metadata_schema()


@mcp.tool
async def submit_security_scan_mcp(
    workflow_name: str,
    target_id: str,
    parameters: Dict[str, Any] | None = None,
) -> Dict[str, Any] | Dict[str, str]:
    """Submit a Temporal workflow via MCP."""
    try:
        not_ready = _temporal_not_ready_status()
        if not_ready:
            return {
                "error": "Temporal infrastructure not ready",
                "temporal": not_ready,
            }

        workflow_info = temporal_mgr.workflows.get(workflow_name)
        if not workflow_info:
            return {"error": f"Workflow '{workflow_name}' not found"}

        metadata = workflow_info.metadata or {}
        defaults = metadata.get("default_parameters", {})

        parameters = parameters or {}
        cleaned_parameters: Dict[str, Any] = {**defaults, **parameters}

        # Ensure *_config structures default to dicts
        for key, value in list(cleaned_parameters.items()):
            if isinstance(key, str) and key.endswith("_config") and value is None:
                cleaned_parameters[key] = {}

        # Some workflows expect configuration dictionaries even when omitted
        parameter_definitions = (
            metadata.get("parameters", {}).get("properties", {})
            if isinstance(metadata.get("parameters"), dict)
            else {}
        )
        for key, definition in parameter_definitions.items():
            if not isinstance(key, str) or not key.endswith("_config"):
                continue
            if key not in cleaned_parameters:
                default_value = definition.get("default") if isinstance(definition, dict) else None
                cleaned_parameters[key] = default_value if default_value is not None else {}
            elif cleaned_parameters[key] is None:
                cleaned_parameters[key] = {}

        # Start workflow
        handle = await temporal_mgr.run_workflow(
            workflow_name=workflow_name,
            target_id=target_id,
            workflow_params=cleaned_parameters,
        )

        return {
            "run_id": handle.id,
            "status": "RUNNING",
            "workflow": workflow_name,
            "message": f"Workflow '{workflow_name}' submitted successfully",
            "target_id": target_id,
            "parameters": cleaned_parameters,
            "mcp_enabled": True,
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("MCP submit failed")
        return {"error": f"Failed to submit workflow: {exc}"}


@mcp.tool
async def get_comprehensive_scan_summary(run_id: str) -> Dict[str, Any] | Dict[str, str]:
    """Return a summary for the given workflow run via MCP."""
    try:
        not_ready = _temporal_not_ready_status()
        if not_ready:
            return {
                "error": "Temporal infrastructure not ready",
                "temporal": not_ready,
            }

        status = await temporal_mgr.get_workflow_status(run_id)

        # Try to get result if completed
        total_findings = 0
        severity_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        if status.get("status") == "COMPLETED":
            try:
                result = await temporal_mgr.get_workflow_result(run_id)
                if isinstance(result, dict):
                    summary = result.get("summary", {})
                    total_findings = summary.get("total_findings", 0)
            except Exception as e:
                logger.debug(f"Could not retrieve result for {run_id}: {e}")

        return {
            "run_id": run_id,
            "workflow": "unknown",  # Temporal doesn't track workflow name in status
            "status": status.get("status", "unknown"),
            "is_completed": status.get("status") == "COMPLETED",
            "total_findings": total_findings,
            "severity_summary": severity_summary,
            "scan_duration": status.get("close_time", "In progress"),
            "recommendations": (
                [
                    "Review high and critical severity findings first",
                    "Implement security fixes based on finding recommendations",
                    "Re-run scan after applying fixes to verify remediation",
                ]
                if total_findings > 0
                else ["No security issues found"]
            ),
            "mcp_analysis": True,
        }
    except Exception as exc:  # pragma: no cover
        logger.exception("MCP summary failed")
        return {"error": f"Failed to summarize run: {exc}"}


@mcp.tool
async def get_run_status_mcp(run_id: str) -> Dict[str, Any]:
    """Return current status information for a Temporal run."""
    try:
        not_ready = _temporal_not_ready_status()
        if not_ready:
            return {
                "error": "Temporal infrastructure not ready",
                "temporal": not_ready,
            }

        status = await temporal_mgr.get_workflow_status(run_id)

        return {
            "run_id": run_id,
            "workflow": "unknown",
            "status": status["status"],
            "is_completed": status["status"] in ["COMPLETED", "FAILED", "CANCELLED"],
            "is_failed": status["status"] == "FAILED",
            "is_running": status["status"] == "RUNNING",
            "created_at": status.get("start_time"),
            "updated_at": status.get("close_time") or status.get("execution_time"),
        }
    except Exception as exc:
        logger.exception("MCP run status failed")
        return {"error": f"Failed to get run status: {exc}"}


@mcp.tool
async def get_run_findings_mcp(run_id: str) -> Dict[str, Any]:
    """Return SARIF findings for a completed run."""
    try:
        not_ready = _temporal_not_ready_status()
        if not_ready:
            return {
                "error": "Temporal infrastructure not ready",
                "temporal": not_ready,
            }

        status = await temporal_mgr.get_workflow_status(run_id)
        if status.get("status") != "COMPLETED":
            return {"error": f"Run {run_id} not completed. Status: {status.get('status')}"}

        result = await temporal_mgr.get_workflow_result(run_id)

        metadata = {
            "completion_time": status.get("close_time"),
            "workflow_version": "unknown",
        }

        sarif = result.get("sarif", {}) if isinstance(result, dict) else {}

        return {
            "workflow": "unknown",
            "run_id": run_id,
            "sarif": sarif,
            "metadata": metadata,
        }
    except Exception as exc:
        logger.exception("MCP findings failed")
        return {"error": f"Failed to retrieve findings: {exc}"}


@mcp.tool
async def list_recent_runs_mcp(
    limit: int = 10,
    workflow_name: str | None = None,
) -> Dict[str, Any]:
    """List recent Temporal runs with optional workflow filter."""

    not_ready = _temporal_not_ready_status()
    if not_ready:
        return {
            "runs": [],
            "temporal": not_ready,
            "message": "Temporal infrastructure is still initializing",
        }

    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = 10
    limit_value = max(1, min(limit_value, 100))

    try:
        # Build filter query
        filter_query = None
        if workflow_name:
            workflow_info = temporal_mgr.workflows.get(workflow_name)
            if workflow_info:
                filter_query = f'WorkflowType="{workflow_info.workflow_type}"'

        workflows = await temporal_mgr.list_workflows(filter_query, limit_value)

        results: List[Dict[str, Any]] = []
        for wf in workflows:
            results.append({
                "run_id": wf["workflow_id"],
                "workflow": workflow_name or "unknown",
                "state": wf["status"],
                "state_type": wf["status"],
                "is_completed": wf["status"] in ["COMPLETED", "FAILED", "CANCELLED"],
                "is_running": wf["status"] == "RUNNING",
                "is_failed": wf["status"] == "FAILED",
                "created_at": wf.get("start_time"),
                "updated_at": wf.get("close_time"),
            })

        return {"runs": results, "temporal": get_temporal_status()}

    except Exception as exc:
        logger.exception("Failed to list runs")
        return {
            "runs": [],
            "temporal": get_temporal_status(),
            "error": str(exc)
        }


@mcp.tool
async def get_fuzzing_stats_mcp(run_id: str) -> Dict[str, Any]:
    """Return fuzzing statistics for a run if available."""
    not_ready = _temporal_not_ready_status()
    if not_ready:
        return {
            "error": "Temporal infrastructure not ready",
            "temporal": not_ready,
        }

    stats = fuzzing.fuzzing_stats.get(run_id)
    if not stats:
        return {"error": f"Fuzzing run not found: {run_id}"}
    # Be resilient if a plain dict slipped into the cache
    if isinstance(stats, dict):
        return stats
    if hasattr(stats, "model_dump"):
        return stats.model_dump()
    if hasattr(stats, "dict"):
        return stats.dict()
    # Last resort
    return getattr(stats, "__dict__", {"run_id": run_id})


@mcp.tool
async def get_fuzzing_crash_reports_mcp(run_id: str) -> Dict[str, Any]:
    """Return crash reports collected for a fuzzing run."""
    not_ready = _temporal_not_ready_status()
    if not_ready:
        return {
            "error": "Temporal infrastructure not ready",
            "temporal": not_ready,
        }

    reports = fuzzing.crash_reports.get(run_id)
    if reports is None:
        return {"error": f"Fuzzing run not found: {run_id}"}
    return {"run_id": run_id, "crashes": [report.model_dump() for report in reports]}


@mcp.tool
async def get_backend_status_mcp() -> Dict[str, Any]:
    """Expose backend readiness, workflows, and registered MCP tools."""

    status = get_temporal_status()
    response: Dict[str, Any] = {"temporal": status}

    if status.get("ready"):
        response["workflows"] = list(temporal_mgr.workflows.keys())

    try:
        tools = await mcp._tool_manager.list_tools()
        response["mcp_tools"] = sorted(tool.name for tool in tools)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Failed to enumerate MCP tools: %s", exc)

    return response


def create_mcp_transport_app() -> Starlette:
    """Build a Starlette app serving HTTP + SSE transports on one port."""

    http_app = mcp.http_app(path="/", transport="streamable-http")
    sse_app = create_sse_app(
        server=mcp,
        message_path="/messages",
        sse_path="/",
        auth=mcp.auth,
    )

    routes = [
        Mount("/mcp", app=http_app),
        Mount("/mcp/sse", app=sse_app),
    ]

    @asynccontextmanager
    async def lifespan(app: Starlette):  # pragma: no cover - integration wiring
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(
                http_app.router.lifespan_context(http_app)
            )
            await stack.enter_async_context(
                sse_app.router.lifespan_context(sse_app)
            )
            yield

    combined_app = Starlette(routes=routes, lifespan=lifespan)
    combined_app.state.fastmcp_server = mcp
    combined_app.state.http_app = http_app
    combined_app.state.sse_app = sse_app
    return combined_app


# ---------------------------------------------------------------------------
# Combined lifespan: Temporal init + dedicated MCP transports
# ---------------------------------------------------------------------------

@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    global temporal_bootstrap_task, _fastapi_mcp_imported

    logger.info("Starting FuzzForge backend...")

    # Ensure FastAPI endpoints are exposed via MCP once
    if not _fastapi_mcp_imported:
        try:
            await mcp.import_server(FASTAPI_MCP_ADAPTER)
            _fastapi_mcp_imported = True
            logger.info("Mounted FastAPI endpoints as MCP tools")
        except Exception as exc:
            logger.exception("Failed to import FastAPI endpoints into MCP", exc_info=exc)

    # Kick off Temporal bootstrap in the background if needed
    if temporal_bootstrap_task is None or temporal_bootstrap_task.done():
        temporal_bootstrap_task = asyncio.create_task(_bootstrap_temporal_with_retries())
        logger.info("Temporal bootstrap task started")
    else:
        logger.info("Temporal bootstrap task already running")

    # Start MCP transports on shared port (HTTP + SSE)
    mcp_app = create_mcp_transport_app()
    mcp_config = uvicorn.Config(
        app=mcp_app,
        host="0.0.0.0",
        port=8010,
        log_level="info",
        lifespan="on",
    )
    mcp_server = uvicorn.Server(mcp_config)
    mcp_server.install_signal_handlers = lambda: None  # type: ignore[assignment]
    mcp_task = asyncio.create_task(mcp_server.serve())

    async def _wait_for_uvicorn_startup() -> None:
        started_attr = getattr(mcp_server, "started", None)
        if hasattr(started_attr, "wait"):
            await asyncio.wait_for(started_attr.wait(), timeout=10)
            return

        # Fallback for uvicorn versions where "started" is a bool
        poll_interval = 0.1
        checks = int(10 / poll_interval)
        for _ in range(checks):
            if getattr(mcp_server, "started", False):
                return
            await asyncio.sleep(poll_interval)
        raise asyncio.TimeoutError

    try:
        await _wait_for_uvicorn_startup()
    except asyncio.TimeoutError:  # pragma: no cover - defensive logging
        if mcp_task.done():
            raise RuntimeError("MCP server failed to start") from mcp_task.exception()
        logger.warning("Timed out waiting for MCP server startup; continuing anyway")

    logger.info("MCP HTTP available at http://0.0.0.0:8010/mcp")
    logger.info("MCP SSE available at http://0.0.0.0:8010/mcp/sse")

    try:
        yield
    finally:
        logger.info("Shutting down MCP transports...")
        mcp_server.should_exit = True
        mcp_server.force_exit = True
        await asyncio.gather(mcp_task, return_exceptions=True)

        if temporal_bootstrap_task and not temporal_bootstrap_task.done():
            temporal_bootstrap_task.cancel()
            with suppress(asyncio.CancelledError):
                await temporal_bootstrap_task
        temporal_bootstrap_state.task_running = False
        if not temporal_bootstrap_state.ready:
            temporal_bootstrap_state.status = "stopped"
        temporal_bootstrap_task = None

        # Close Temporal client
        await temporal_mgr.close()
        logger.info("Shutting down FuzzForge backend...")


app.router.lifespan_context = combined_lifespan
