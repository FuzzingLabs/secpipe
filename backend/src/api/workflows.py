"""
API endpoints for workflow management with enhanced error handling
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
import traceback
import tempfile
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pathlib import Path

from src.models.findings import (
    WorkflowSubmission,
    WorkflowMetadata,
    WorkflowListItem,
    RunSubmissionResponse
)
from src.temporal.discovery import WorkflowDiscovery

logger = logging.getLogger(__name__)

# Configuration for file uploads
MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
ALLOWED_CONTENT_TYPES = [
    "application/gzip",
    "application/x-gzip",
    "application/x-tar",
    "application/x-compressed-tar",
    "application/octet-stream",  # Generic binary
]

router = APIRouter(prefix="/workflows", tags=["workflows"])


def create_structured_error_response(
    error_type: str,
    message: str,
    workflow_name: Optional[str] = None,
    run_id: Optional[str] = None,
    container_info: Optional[Dict[str, Any]] = None,
    deployment_info: Optional[Dict[str, Any]] = None,
    suggestions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create a structured error response with rich context."""
    error_response = {
        "error": {
            "type": error_type,
            "message": message,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
    }

    if workflow_name:
        error_response["error"]["workflow_name"] = workflow_name

    if run_id:
        error_response["error"]["run_id"] = run_id

    if container_info:
        error_response["error"]["container"] = container_info

    if deployment_info:
        error_response["error"]["deployment"] = deployment_info

    if suggestions:
        error_response["error"]["suggestions"] = suggestions

    return error_response


def get_temporal_manager():
    """Dependency to get the Temporal manager instance"""
    from src.main import temporal_mgr
    return temporal_mgr


@router.get("/", response_model=List[WorkflowListItem])
async def list_workflows(
    temporal_mgr=Depends(get_temporal_manager)
) -> List[WorkflowListItem]:
    """
    List all discovered workflows with their metadata.

    Returns a summary of each workflow including name, version, description,
    author, and tags.
    """
    workflows = []
    for name, info in temporal_mgr.workflows.items():
        workflows.append(WorkflowListItem(
            name=name,
            version=info.metadata.get("version", "0.6.0"),
            description=info.metadata.get("description", ""),
            author=info.metadata.get("author"),
            tags=info.metadata.get("tags", [])
        ))

    return workflows


@router.get("/metadata/schema")
async def get_metadata_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for workflow metadata files.

    This schema defines the structure and requirements for metadata.yaml files
    that must accompany each workflow.
    """
    return WorkflowDiscovery.get_metadata_schema()


@router.get("/{workflow_name}/metadata", response_model=WorkflowMetadata)
async def get_workflow_metadata(
    workflow_name: str,
    temporal_mgr=Depends(get_temporal_manager)
) -> WorkflowMetadata:
    """
    Get complete metadata for a specific workflow.

    Args:
        workflow_name: Name of the workflow

    Returns:
        Complete metadata including parameters schema, supported volume modes,
        required modules, and more.

    Raises:
        HTTPException: 404 if workflow not found
    """
    if workflow_name not in temporal_mgr.workflows:
        available_workflows = list(temporal_mgr.workflows.keys())
        error_response = create_structured_error_response(
            error_type="WorkflowNotFound",
            message=f"Workflow '{workflow_name}' not found",
            workflow_name=workflow_name,
            suggestions=[
                f"Available workflows: {', '.join(available_workflows)}",
                "Use GET /workflows/ to see all available workflows",
                "Check workflow name spelling and case sensitivity"
            ]
        )
        raise HTTPException(
            status_code=404,
            detail=error_response
        )

    info = temporal_mgr.workflows[workflow_name]
    metadata = info.metadata

    return WorkflowMetadata(
        name=workflow_name,
        version=metadata.get("version", "0.6.0"),
        description=metadata.get("description", ""),
        author=metadata.get("author"),
        tags=metadata.get("tags", []),
        parameters=metadata.get("parameters", {}),
        default_parameters=metadata.get("default_parameters", {}),
        required_modules=metadata.get("required_modules", [])
    )


@router.post("/{workflow_name}/submit", response_model=RunSubmissionResponse)
async def submit_workflow(
    workflow_name: str,
    submission: WorkflowSubmission,
    temporal_mgr=Depends(get_temporal_manager)
) -> RunSubmissionResponse:
    """
    Submit a workflow for execution.

    Args:
        workflow_name: Name of the workflow to execute
        submission: Submission parameters including target path and parameters

    Returns:
        Run submission response with run_id and initial status

    Raises:
        HTTPException: 404 if workflow not found, 400 for invalid parameters
    """
    if workflow_name not in temporal_mgr.workflows:
        available_workflows = list(temporal_mgr.workflows.keys())
        error_response = create_structured_error_response(
            error_type="WorkflowNotFound",
            message=f"Workflow '{workflow_name}' not found",
            workflow_name=workflow_name,
            suggestions=[
                f"Available workflows: {', '.join(available_workflows)}",
                "Use GET /workflows/ to see all available workflows",
                "Check workflow name spelling and case sensitivity"
            ]
        )
        raise HTTPException(
            status_code=404,
            detail=error_response
        )

    try:
        # Upload target file to MinIO and get target_id
        target_path = Path(submission.target_path)
        if not target_path.exists():
            raise ValueError(f"Target path does not exist: {submission.target_path}")

        # Upload target (using anonymous user for now)
        target_id = await temporal_mgr.upload_target(
            file_path=target_path,
            user_id="api-user",
            metadata={"workflow": workflow_name}
        )

        # Merge default parameters with user parameters
        workflow_info = temporal_mgr.workflows[workflow_name]
        metadata = workflow_info.metadata or {}
        defaults = metadata.get("default_parameters", {})
        user_params = submission.parameters or {}
        workflow_params = {**defaults, **user_params}

        # Start workflow execution
        handle = await temporal_mgr.run_workflow(
            workflow_name=workflow_name,
            target_id=target_id,
            workflow_params=workflow_params
        )

        run_id = handle.id

        # Initialize fuzzing tracking if this looks like a fuzzing workflow
        workflow_info = temporal_mgr.workflows.get(workflow_name, {})
        workflow_tags = workflow_info.metadata.get("tags", []) if hasattr(workflow_info, 'metadata') else []
        if "fuzzing" in workflow_tags or "fuzz" in workflow_name.lower():
            from src.api.fuzzing import initialize_fuzzing_tracking
            initialize_fuzzing_tracking(run_id, workflow_name)

        return RunSubmissionResponse(
            run_id=run_id,
            status="RUNNING",
            workflow=workflow_name,
            message=f"Workflow '{workflow_name}' submitted successfully"
        )

    except ValueError as e:
        # Parameter validation errors
        error_response = create_structured_error_response(
            error_type="ValidationError",
            message=str(e),
            workflow_name=workflow_name,
            suggestions=[
                "Check parameter types and values",
                "Use GET /workflows/{workflow_name}/parameters for schema",
                "Ensure all required parameters are provided"
            ]
        )
        raise HTTPException(status_code=400, detail=error_response)

    except Exception as e:
        logger.error(f"Failed to submit workflow '{workflow_name}': {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Try to get more context about the error
        container_info = None
        deployment_info = None
        suggestions = []

        error_message = str(e)
        error_type = "WorkflowSubmissionError"

        # Detect specific error patterns
        if "workflow" in error_message.lower() and "not found" in error_message.lower():
            error_type = "WorkflowError"
            suggestions.extend([
                "Check if Temporal server is running and accessible",
                "Verify workflow workers are running",
                "Check if workflow is registered with correct vertical",
                "Ensure Docker is running and has sufficient resources"
            ])

        elif "volume" in error_message.lower() or "mount" in error_message.lower():
            error_type = "VolumeError"
            suggestions.extend([
                "Check if the target path exists and is accessible",
                "Verify file permissions (Docker needs read access)",
                "Ensure the path is not in use by another process",
                "Try using an absolute path instead of relative path"
            ])

        elif "memory" in error_message.lower() or "resource" in error_message.lower():
            error_type = "ResourceError"
            suggestions.extend([
                "Check system memory and CPU availability",
                "Consider reducing resource limits or dataset size",
                "Monitor Docker resource usage",
                "Increase Docker memory limits if needed"
            ])

        elif "image" in error_message.lower():
            error_type = "ImageError"
            suggestions.extend([
                "Check if the workflow image exists",
                "Verify Docker registry access",
                "Try rebuilding the workflow image",
                "Check network connectivity to registries"
            ])

        else:
            suggestions.extend([
                "Check FuzzForge backend logs for details",
                "Verify all services are running (docker-compose up -d)",
                "Try restarting the workflow deployment",
                "Contact support if the issue persists"
            ])

        error_response = create_structured_error_response(
            error_type=error_type,
            message=f"Failed to submit workflow: {error_message}",
            workflow_name=workflow_name,
            container_info=container_info,
            deployment_info=deployment_info,
            suggestions=suggestions
        )

        raise HTTPException(
            status_code=500,
            detail=error_response
        )


@router.post("/{workflow_name}/upload-and-submit", response_model=RunSubmissionResponse)
async def upload_and_submit_workflow(
    workflow_name: str,
    file: UploadFile = File(..., description="Target file or tarball to analyze"),
    parameters: Optional[str] = Form(None, description="JSON-encoded workflow parameters"),
    timeout: Optional[int] = Form(None, description="Timeout in seconds"),
    temporal_mgr=Depends(get_temporal_manager)
) -> RunSubmissionResponse:
    """
    Upload a target file/tarball and submit workflow for execution.

    This endpoint accepts multipart/form-data uploads and is the recommended
    way to submit workflows from remote CLI clients.

    Args:
        workflow_name: Name of the workflow to execute
        file: Target file or tarball (compressed directory)
        parameters: JSON string of workflow parameters (optional)
        timeout: Execution timeout in seconds (optional)

    Returns:
        Run submission response with run_id and initial status

    Raises:
        HTTPException: 404 if workflow not found, 400 for invalid parameters,
                      413 if file too large
    """
    if workflow_name not in temporal_mgr.workflows:
        available_workflows = list(temporal_mgr.workflows.keys())
        error_response = create_structured_error_response(
            error_type="WorkflowNotFound",
            message=f"Workflow '{workflow_name}' not found",
            workflow_name=workflow_name,
            suggestions=[
                f"Available workflows: {', '.join(available_workflows)}",
                "Use GET /workflows/ to see all available workflows"
            ]
        )
        raise HTTPException(status_code=404, detail=error_response)

    temp_file_path = None

    try:
        # Validate file size
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        # Create temporary file
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=".tar.gz")

        logger.info(f"Receiving file upload for workflow '{workflow_name}': {file.filename}")

        # Stream file to disk
        with open(temp_fd, 'wb') as temp_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                file_size += len(chunk)

                # Check size limit
                if file_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=create_structured_error_response(
                            error_type="FileTooLarge",
                            message=f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE / (1024**3):.1f} GB",
                            workflow_name=workflow_name,
                            suggestions=[
                                "Reduce the size of your target directory",
                                "Exclude unnecessary files (build artifacts, dependencies, etc.)",
                                "Consider splitting into smaller analysis targets"
                            ]
                        )
                    )

                temp_file.write(chunk)

        logger.info(f"Received file: {file_size / (1024**2):.2f} MB")

        # Parse parameters
        workflow_params = {}
        if parameters:
            try:
                import json
                workflow_params = json.loads(parameters)
                if not isinstance(workflow_params, dict):
                    raise ValueError("Parameters must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=create_structured_error_response(
                        error_type="InvalidParameters",
                        message=f"Invalid parameters JSON: {e}",
                        workflow_name=workflow_name,
                        suggestions=["Ensure parameters is valid JSON object"]
                    )
                )

        # Upload to MinIO
        target_id = await temporal_mgr.upload_target(
            file_path=Path(temp_file_path),
            user_id="api-user",
            metadata={
                "workflow": workflow_name,
                "original_filename": file.filename,
                "upload_method": "multipart"
            }
        )

        logger.info(f"Uploaded to MinIO with target_id: {target_id}")

        # Merge default parameters with user parameters
        workflow_info = temporal_mgr.workflows.get(workflow_name)
        metadata = workflow_info.metadata or {}
        defaults = metadata.get("default_parameters", {})
        workflow_params = {**defaults, **workflow_params}

        # Start workflow execution
        handle = await temporal_mgr.run_workflow(
            workflow_name=workflow_name,
            target_id=target_id,
            workflow_params=workflow_params
        )

        run_id = handle.id

        # Initialize fuzzing tracking if needed
        workflow_info = temporal_mgr.workflows.get(workflow_name, {})
        workflow_tags = workflow_info.metadata.get("tags", []) if hasattr(workflow_info, 'metadata') else []
        if "fuzzing" in workflow_tags or "fuzz" in workflow_name.lower():
            from src.api.fuzzing import initialize_fuzzing_tracking
            initialize_fuzzing_tracking(run_id, workflow_name)

        return RunSubmissionResponse(
            run_id=run_id,
            status="RUNNING",
            workflow=workflow_name,
            message=f"Workflow '{workflow_name}' submitted successfully with uploaded target"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload and submit workflow '{workflow_name}': {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        error_response = create_structured_error_response(
            error_type="WorkflowSubmissionError",
            message=f"Failed to process upload and submit workflow: {str(e)}",
            workflow_name=workflow_name,
            suggestions=[
                "Check if the uploaded file is a valid tarball",
                "Verify MinIO storage is accessible",
                "Check backend logs for detailed error information",
                "Ensure Temporal workers are running"
            ]
        )

        raise HTTPException(status_code=500, detail=error_response)

    finally:
        # Cleanup temporary file
        if temp_file_path and Path(temp_file_path).exists():
            try:
                Path(temp_file_path).unlink()
                logger.debug(f"Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")


@router.get("/{workflow_name}/worker-info")
async def get_workflow_worker_info(
    workflow_name: str,
    temporal_mgr=Depends(get_temporal_manager)
) -> Dict[str, Any]:
    """
    Get worker information for a workflow.

    Returns details about which worker is required to execute this workflow,
    including container name, task queue, and vertical.

    Args:
        workflow_name: Name of the workflow

    Returns:
        Worker information including vertical, container name, and task queue

    Raises:
        HTTPException: 404 if workflow not found
    """
    if workflow_name not in temporal_mgr.workflows:
        available_workflows = list(temporal_mgr.workflows.keys())
        error_response = create_structured_error_response(
            error_type="WorkflowNotFound",
            message=f"Workflow '{workflow_name}' not found",
            workflow_name=workflow_name,
            suggestions=[
                f"Available workflows: {', '.join(available_workflows)}",
                "Use GET /workflows/ to see all available workflows"
            ]
        )
        raise HTTPException(
            status_code=404,
            detail=error_response
        )

    info = temporal_mgr.workflows[workflow_name]
    metadata = info.metadata

    # Extract vertical from metadata
    vertical = metadata.get("vertical")

    if not vertical:
        error_response = create_structured_error_response(
            error_type="MissingVertical",
            message=f"Workflow '{workflow_name}' does not specify a vertical in metadata",
            workflow_name=workflow_name,
            suggestions=[
                "Check workflow metadata.yaml for 'vertical' field",
                "Contact workflow author for support"
            ]
        )
        raise HTTPException(
            status_code=500,
            detail=error_response
        )

    return {
        "workflow": workflow_name,
        "vertical": vertical,
        "worker_service": f"worker-{vertical}",
        "task_queue": f"{vertical}-queue",
        "required": True
    }


@router.get("/{workflow_name}/parameters")
async def get_workflow_parameters(
    workflow_name: str,
    temporal_mgr=Depends(get_temporal_manager)
) -> Dict[str, Any]:
    """
    Get the parameters schema for a workflow.

    Args:
        workflow_name: Name of the workflow

    Returns:
        Parameters schema with types, descriptions, and defaults

    Raises:
        HTTPException: 404 if workflow not found
    """
    if workflow_name not in temporal_mgr.workflows:
        available_workflows = list(temporal_mgr.workflows.keys())
        error_response = create_structured_error_response(
            error_type="WorkflowNotFound",
            message=f"Workflow '{workflow_name}' not found",
            workflow_name=workflow_name,
            suggestions=[
                f"Available workflows: {', '.join(available_workflows)}",
                "Use GET /workflows/ to see all available workflows"
            ]
        )
        raise HTTPException(
            status_code=404,
            detail=error_response
        )

    info = temporal_mgr.workflows[workflow_name]
    metadata = info.metadata

    # Return parameters with enhanced schema information
    parameters_schema = metadata.get("parameters", {})

    # Extract the actual parameter definitions from JSON schema structure
    if "properties" in parameters_schema:
        param_definitions = parameters_schema["properties"]
    else:
        param_definitions = parameters_schema

    # Add default values to the schema
    default_params = metadata.get("default_parameters", {})
    for param_name, param_schema in param_definitions.items():
        if isinstance(param_schema, dict) and param_name in default_params:
            param_schema["default"] = default_params[param_name]

    return {
        "workflow": workflow_name,
        "parameters": param_definitions,
        "default_parameters": default_params,
        "required_parameters": [
            name for name, schema in param_definitions.items()
            if isinstance(schema, dict) and schema.get("required", False)
        ]
    }