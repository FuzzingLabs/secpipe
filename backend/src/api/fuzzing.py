"""
API endpoints for fuzzing workflow management and real-time monitoring
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

import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import asyncio
import json
from datetime import datetime

from src.models.findings import (
    FuzzingStats,
    CrashReport
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuzzing", tags=["fuzzing"])

# In-memory storage for real-time stats (in production, use Redis or similar)
fuzzing_stats: Dict[str, FuzzingStats] = {}
crash_reports: Dict[str, List[CrashReport]] = {}
active_connections: Dict[str, List[WebSocket]] = {}


def initialize_fuzzing_tracking(run_id: str, workflow_name: str):
    """
    Initialize fuzzing tracking for a new run.

    This function should be called when a workflow is submitted to enable
    real-time monitoring and stats collection.

    Args:
        run_id: The run identifier
        workflow_name: Name of the workflow
    """
    fuzzing_stats[run_id] = FuzzingStats(
        run_id=run_id,
        workflow=workflow_name
    )
    crash_reports[run_id] = []
    active_connections[run_id] = []


@router.get("/{run_id}/stats", response_model=FuzzingStats)
async def get_fuzzing_stats(run_id: str) -> FuzzingStats:
    """
    Get current fuzzing statistics for a run.

    Args:
        run_id: The fuzzing run ID

    Returns:
        Current fuzzing statistics

    Raises:
        HTTPException: 404 if run not found
    """
    if run_id not in fuzzing_stats:
        raise HTTPException(
            status_code=404,
            detail=f"Fuzzing run not found: {run_id}"
        )

    return fuzzing_stats[run_id]


@router.get("/{run_id}/crashes", response_model=List[CrashReport])
async def get_crash_reports(run_id: str) -> List[CrashReport]:
    """
    Get crash reports for a fuzzing run.

    Args:
        run_id: The fuzzing run ID

    Returns:
        List of crash reports

    Raises:
        HTTPException: 404 if run not found
    """
    if run_id not in crash_reports:
        raise HTTPException(
            status_code=404,
            detail=f"Fuzzing run not found: {run_id}"
        )

    return crash_reports[run_id]


@router.post("/{run_id}/stats")
async def update_fuzzing_stats(run_id: str, stats: FuzzingStats):
    """
    Update fuzzing statistics (called by fuzzing workflows).

    Args:
        run_id: The fuzzing run ID
        stats: Updated statistics

    Raises:
        HTTPException: 404 if run not found
    """
    if run_id not in fuzzing_stats:
        raise HTTPException(
            status_code=404,
            detail=f"Fuzzing run not found: {run_id}"
        )

    # Update stats
    fuzzing_stats[run_id] = stats

    # Debug: log reception for live instrumentation
    try:
        logger.info(
            "Received fuzzing stats update: run_id=%s exec=%s eps=%.2f crashes=%s corpus=%s coverage=%s elapsed=%ss",
            run_id,
            stats.executions,
            stats.executions_per_sec,
            stats.crashes,
            stats.corpus_size,
            stats.coverage,
            stats.elapsed_time,
        )
    except Exception:
        pass

    # Notify connected WebSocket clients
    if run_id in active_connections:
        message = {
            "type": "stats_update",
            "data": stats.model_dump()
        }
        for websocket in active_connections[run_id][:]:  # Copy to avoid modification during iteration
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                # Remove disconnected clients
                active_connections[run_id].remove(websocket)


@router.post("/{run_id}/crash")
async def report_crash(run_id: str, crash: CrashReport):
    """
    Report a new crash (called by fuzzing workflows).

    Args:
        run_id: The fuzzing run ID
        crash: Crash report details
    """
    if run_id not in crash_reports:
        crash_reports[run_id] = []

    # Add crash report
    crash_reports[run_id].append(crash)

    # Update stats
    if run_id in fuzzing_stats:
        fuzzing_stats[run_id].crashes += 1
        fuzzing_stats[run_id].last_crash_time = crash.timestamp

    # Notify connected WebSocket clients
    if run_id in active_connections:
        message = {
            "type": "crash_report",
            "data": crash.model_dump()
        }
        for websocket in active_connections[run_id][:]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                active_connections[run_id].remove(websocket)


@router.websocket("/{run_id}/live")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time fuzzing updates.

    Args:
        websocket: WebSocket connection
        run_id: The fuzzing run ID to monitor
    """
    await websocket.accept()

    # Initialize connection tracking
    if run_id not in active_connections:
        active_connections[run_id] = []
    active_connections[run_id].append(websocket)

    try:
        # Send current stats on connection
        if run_id in fuzzing_stats:
            current = fuzzing_stats[run_id]
            if isinstance(current, dict):
                payload = current
            elif hasattr(current, "model_dump"):
                payload = current.model_dump()
            elif hasattr(current, "dict"):
                payload = current.dict()
            else:
                payload = getattr(current, "__dict__", {"run_id": run_id})
            message = {"type": "stats_update", "data": payload}
            await websocket.send_text(json.dumps(message))

        # Keep connection alive
        while True:
            try:
                # Wait for ping or handle disconnect
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back for ping-pong
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_text(json.dumps({"type": "heartbeat"}))

    except WebSocketDisconnect:
        # Clean up connection
        if run_id in active_connections and websocket in active_connections[run_id]:
            active_connections[run_id].remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
        if run_id in active_connections and websocket in active_connections[run_id]:
            active_connections[run_id].remove(websocket)


@router.get("/{run_id}/stream")
async def stream_fuzzing_updates(run_id: str):
    """
    Server-Sent Events endpoint for real-time fuzzing updates.

    Args:
        run_id: The fuzzing run ID to monitor

    Returns:
        Streaming response with real-time updates
    """
    if run_id not in fuzzing_stats:
        raise HTTPException(
            status_code=404,
            detail=f"Fuzzing run not found: {run_id}"
        )

    async def event_stream():
        """Generate server-sent events for fuzzing updates"""
        last_stats_time = datetime.utcnow()

        while True:
            try:
                # Send current stats
                if run_id in fuzzing_stats:
                    current_stats = fuzzing_stats[run_id]
                    if isinstance(current_stats, dict):
                        stats_payload = current_stats
                    elif hasattr(current_stats, "model_dump"):
                        stats_payload = current_stats.model_dump()
                    elif hasattr(current_stats, "dict"):
                        stats_payload = current_stats.dict()
                    else:
                        stats_payload = getattr(current_stats, "__dict__", {"run_id": run_id})
                    event_data = f"data: {json.dumps({'type': 'stats', 'data': stats_payload})}\n\n"
                    yield event_data

                # Send recent crashes
                if run_id in crash_reports:
                    recent_crashes = [
                        crash for crash in crash_reports[run_id]
                        if crash.timestamp > last_stats_time
                    ]
                    for crash in recent_crashes:
                        event_data = f"data: {json.dumps({'type': 'crash', 'data': crash.model_dump()})}\n\n"
                        yield event_data

                last_stats_time = datetime.utcnow()
                await asyncio.sleep(5)  # Update every 5 seconds

            except Exception as e:
                logger.error(f"Error in event stream for run {run_id}: {e}")
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.delete("/{run_id}")
async def cleanup_fuzzing_run(run_id: str):
    """
    Clean up fuzzing run data.

    Args:
        run_id: The fuzzing run ID to clean up
    """
    # Clean up tracking data
    fuzzing_stats.pop(run_id, None)
    crash_reports.pop(run_id, None)

    # Close any active WebSocket connections
    if run_id in active_connections:
        for websocket in active_connections[run_id]:
            try:
                await websocket.close()
            except Exception:
                pass
        del active_connections[run_id]

    return {"message": f"Cleaned up fuzzing run {run_id}"}
