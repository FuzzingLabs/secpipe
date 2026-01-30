"""
API endpoints for workflow run management and findings retrieval
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
from fastapi import APIRouter, HTTPException, Depends

from src.models.findings import WorkflowFindings, WorkflowStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


def get_temporal_manager():
    """Dependency to get the Temporal manager instance"""
    from src.main import temporal_mgr
    return temporal_mgr


@router.get("/{run_id}/status", response_model=WorkflowStatus)
async def get_run_status(
    run_id: str,
    temporal_mgr=Depends(get_temporal_manager)
) -> WorkflowStatus:
    """
    Get the current status of a workflow run.

    Args:
        run_id: The workflow run ID

    Returns:
        Status information including state, timestamps, and completion flags

    Raises:
        HTTPException: 404 if run not found
    """
    try:
        status = await temporal_mgr.get_workflow_status(run_id)

        # Map Temporal status to response format
        workflow_status = status.get("status", "UNKNOWN")
        is_completed = workflow_status in ["COMPLETED", "FAILED", "CANCELLED"]
        is_failed = workflow_status == "FAILED"
        is_running = workflow_status == "RUNNING"

        # Extract workflow name from run_id (format: workflow_name-unique_id)
        workflow_name = run_id.rsplit('-', 1)[0] if '-' in run_id else "unknown"

        return WorkflowStatus(
            run_id=run_id,
            workflow=workflow_name,
            status=workflow_status,
            is_completed=is_completed,
            is_failed=is_failed,
            is_running=is_running,
            created_at=status.get("start_time"),
            updated_at=status.get("close_time") or status.get("execution_time")
        )

    except Exception as e:
        logger.error(f"Failed to get status for run {run_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Run not found: {run_id}"
        )


@router.get("/{run_id}/findings", response_model=WorkflowFindings)
async def get_run_findings(
    run_id: str,
    temporal_mgr=Depends(get_temporal_manager)
) -> WorkflowFindings:
    """
    Get the findings from a completed workflow run.

    Args:
        run_id: The workflow run ID

    Returns:
        SARIF-formatted findings from the workflow execution

    Raises:
        HTTPException: 404 if run not found, 400 if run not completed
    """
    try:
        # Get run status first
        status = await temporal_mgr.get_workflow_status(run_id)
        workflow_status = status.get("status", "UNKNOWN")

        if workflow_status not in ["COMPLETED", "FAILED", "CANCELLED"]:
            if workflow_status == "RUNNING":
                raise HTTPException(
                    status_code=400,
                    detail=f"Run {run_id} is still running. Current status: {workflow_status}"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Run {run_id} not completed. Status: {workflow_status}"
                )

        if workflow_status == "FAILED":
            raise HTTPException(
                status_code=400,
                detail=f"Run {run_id} failed. Status: {workflow_status}"
            )

        # Get the workflow result
        result = await temporal_mgr.get_workflow_result(run_id)

        # Extract SARIF from result (handle None for backwards compatibility)
        if isinstance(result, dict):
            sarif = result.get("sarif") or {}
        else:
            sarif = {}

        # Extract workflow name from run_id (format: workflow_name-unique_id)
        workflow_name = run_id.rsplit('-', 1)[0] if '-' in run_id else "unknown"

        # Metadata
        metadata = {
            "completion_time": status.get("close_time"),
            "workflow_version": "unknown"
        }

        return WorkflowFindings(
            workflow=workflow_name,
            run_id=run_id,
            sarif=sarif,
            metadata=metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get findings for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve findings: {str(e)}"
        )


@router.get("/{workflow_name}/findings/{run_id}", response_model=WorkflowFindings)
async def get_workflow_findings(
    workflow_name: str,
    run_id: str,
    temporal_mgr=Depends(get_temporal_manager)
) -> WorkflowFindings:
    """
    Get findings for a specific workflow run.

    Alternative endpoint that includes workflow name in the path for clarity.

    Args:
        workflow_name: Name of the workflow
        run_id: The workflow run ID

    Returns:
        SARIF-formatted findings from the workflow execution

    Raises:
        HTTPException: 404 if workflow or run not found, 400 if run not completed
    """
    if workflow_name not in temporal_mgr.workflows:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_name}"
        )

    # Delegate to the main findings endpoint
    return await get_run_findings(run_id, temporal_mgr)
