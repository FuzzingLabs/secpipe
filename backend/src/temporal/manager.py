"""
Temporal Manager - Workflow execution and management

Handles:
- Workflow discovery from toolbox
- Workflow execution (submit to Temporal)
- Status monitoring
- Results retrieval
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any
from uuid import uuid4

from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from datetime import timedelta

from .discovery import WorkflowDiscovery, WorkflowInfo
from src.storage import S3CachedStorage

logger = logging.getLogger(__name__)


class TemporalManager:
    """
    Manages Temporal workflow execution for FuzzForge.

    This class:
    - Discovers available workflows from toolbox
    - Submits workflow executions to Temporal
    - Monitors workflow status
    - Retrieves workflow results
    """

    def __init__(
        self,
        workflows_dir: Optional[Path] = None,
        temporal_address: Optional[str] = None,
        temporal_namespace: str = "default",
        storage: Optional[S3CachedStorage] = None
    ):
        """
        Initialize Temporal manager.

        Args:
            workflows_dir: Path to workflows directory (default: toolbox/workflows)
            temporal_address: Temporal server address (default: from env or localhost:7233)
            temporal_namespace: Temporal namespace
            storage: Storage backend for file uploads (default: S3CachedStorage)
        """
        if workflows_dir is None:
            workflows_dir = Path("toolbox/workflows")

        self.temporal_address = temporal_address or os.getenv(
            'TEMPORAL_ADDRESS',
            'localhost:7233'
        )
        self.temporal_namespace = temporal_namespace
        self.discovery = WorkflowDiscovery(workflows_dir)
        self.workflows: Dict[str, WorkflowInfo] = {}
        self.client: Optional[Client] = None

        # Initialize storage backend
        self.storage = storage or S3CachedStorage()

        logger.info(
            f"TemporalManager initialized: {self.temporal_address} "
            f"(namespace: {self.temporal_namespace})"
        )

    async def initialize(self):
        """Initialize the manager by discovering workflows and connecting to Temporal."""
        try:
            # Discover workflows
            self.workflows = await self.discovery.discover_workflows()

            if not self.workflows:
                logger.warning("No workflows discovered")
            else:
                logger.info(
                    f"Discovered {len(self.workflows)} workflows: "
                    f"{list(self.workflows.keys())}"
                )

            # Connect to Temporal
            self.client = await Client.connect(
                self.temporal_address,
                namespace=self.temporal_namespace
            )
            logger.info(f"✓ Connected to Temporal: {self.temporal_address}")

        except Exception as e:
            logger.error(f"Failed to initialize Temporal manager: {e}", exc_info=True)
            raise

    async def close(self):
        """Close Temporal client connection."""
        if self.client:
            # Temporal client doesn't need explicit close in Python SDK
            pass

    async def get_workflows(self) -> Dict[str, WorkflowInfo]:
        """
        Get all discovered workflows.

        Returns:
            Dictionary mapping workflow names to their info
        """
        return self.workflows

    async def get_workflow(self, name: str) -> Optional[WorkflowInfo]:
        """
        Get workflow info by name.

        Args:
            name: Workflow name

        Returns:
            WorkflowInfo or None if not found
        """
        return self.workflows.get(name)

    async def upload_target(
        self,
        file_path: Path,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload target file to storage.

        Args:
            file_path: Local path to file
            user_id: User ID
            metadata: Optional metadata

        Returns:
            Target ID for use in workflow execution
        """
        target_id = await self.storage.upload_target(file_path, user_id, metadata)
        logger.info(f"Uploaded target: {target_id}")
        return target_id

    async def run_workflow(
        self,
        workflow_name: str,
        target_id: str,
        workflow_params: Optional[Dict[str, Any]] = None,
        workflow_id: Optional[str] = None
    ) -> WorkflowHandle:
        """
        Execute a workflow.

        Args:
            workflow_name: Name of workflow to execute
            target_id: Target ID (from upload_target)
            workflow_params: Additional workflow parameters
            workflow_id: Optional workflow ID (generated if not provided)

        Returns:
            WorkflowHandle for monitoring/results

        Raises:
            ValueError: If workflow not found or client not initialized
        """
        if not self.client:
            raise ValueError("Temporal client not initialized. Call initialize() first.")

        # Get workflow info
        workflow_info = self.workflows.get(workflow_name)
        if not workflow_info:
            raise ValueError(f"Workflow not found: {workflow_name}")

        # Generate workflow ID if not provided
        if not workflow_id:
            workflow_id = f"{workflow_name}-{str(uuid4())[:8]}"

        # Prepare workflow input arguments
        workflow_params = workflow_params or {}

        # Build args list: [target_id, ...workflow_params in schema order]
        # The workflow parameters are passed as individual positional args
        workflow_args = [target_id]

        # Add parameters in order based on metadata schema
        # This ensures parameters match the workflow signature order
        if workflow_params and 'parameters' in workflow_info.metadata:
            param_schema = workflow_info.metadata['parameters'].get('properties', {})
            # Iterate parameters in schema order and add values
            for param_name in param_schema.keys():
                param_value = workflow_params.get(param_name)
                workflow_args.append(param_value)

        # Determine task queue from workflow vertical
        vertical = workflow_info.metadata.get("vertical", "default")
        task_queue = f"{vertical}-queue"

        logger.info(
            f"Starting workflow: {workflow_name} "
            f"(id={workflow_id}, queue={task_queue}, target={target_id})"
        )
        logger.info(f"DEBUG: workflow_args = {workflow_args}")
        logger.info(f"DEBUG: workflow_params received = {workflow_params}")

        try:
            # Start workflow execution with positional arguments
            handle = await self.client.start_workflow(
                workflow=workflow_info.workflow_type,  # Workflow class name
                args=workflow_args,  # Positional arguments
                id=workflow_id,
                task_queue=task_queue,
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3
                )
            )

            logger.info(f"✓ Workflow started: {workflow_id}")
            return handle

        except Exception as e:
            logger.error(f"Failed to start workflow {workflow_name}: {e}", exc_info=True)
            raise

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow execution status.

        Args:
            workflow_id: Workflow execution ID

        Returns:
            Status dictionary with workflow state

        Raises:
            ValueError: If client not initialized or workflow not found
        """
        if not self.client:
            raise ValueError("Temporal client not initialized")

        try:
            # Get workflow handle
            handle = self.client.get_workflow_handle(workflow_id)

            # Try to get result (non-blocking describe)
            description = await handle.describe()

            status = {
                "workflow_id": workflow_id,
                "status": description.status.name,
                "start_time": description.start_time.isoformat() if description.start_time else None,
                "execution_time": description.execution_time.isoformat() if description.execution_time else None,
                "close_time": description.close_time.isoformat() if description.close_time else None,
                "task_queue": description.task_queue,
            }

            logger.info(f"Workflow {workflow_id} status: {status['status']}")
            return status

        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}", exc_info=True)
            raise

    async def get_workflow_result(
        self,
        workflow_id: str,
        timeout: Optional[timedelta] = None
    ) -> Any:
        """
        Get workflow execution result (blocking).

        Args:
            workflow_id: Workflow execution ID
            timeout: Maximum time to wait for result

        Returns:
            Workflow result

        Raises:
            ValueError: If client not initialized
            TimeoutError: If timeout exceeded
        """
        if not self.client:
            raise ValueError("Temporal client not initialized")

        try:
            handle = self.client.get_workflow_handle(workflow_id)

            logger.info(f"Waiting for workflow result: {workflow_id}")

            # Wait for workflow to complete and get result
            if timeout:
                # Use asyncio timeout if provided
                import asyncio
                result = await asyncio.wait_for(handle.result(), timeout=timeout.total_seconds())
            else:
                result = await handle.result()

            logger.info(f"✓ Workflow {workflow_id} completed")
            return result

        except Exception as e:
            logger.error(f"Failed to get workflow result: {e}", exc_info=True)
            raise

    async def cancel_workflow(self, workflow_id: str) -> None:
        """
        Cancel a running workflow.

        Args:
            workflow_id: Workflow execution ID

        Raises:
            ValueError: If client not initialized
        """
        if not self.client:
            raise ValueError("Temporal client not initialized")

        try:
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.cancel()

            logger.info(f"✓ Workflow cancelled: {workflow_id}")

        except Exception as e:
            logger.error(f"Failed to cancel workflow: {e}", exc_info=True)
            raise

    async def list_workflows(
        self,
        filter_query: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        List workflow executions.

        Args:
            filter_query: Optional Temporal list filter query
            limit: Maximum number of results

        Returns:
            List of workflow execution info

        Raises:
            ValueError: If client not initialized
        """
        if not self.client:
            raise ValueError("Temporal client not initialized")

        try:
            workflows = []

            # Use Temporal's list API
            async for workflow in self.client.list_workflows(filter_query):
                workflows.append({
                    "workflow_id": workflow.id,
                    "workflow_type": workflow.workflow_type,
                    "status": workflow.status.name,
                    "start_time": workflow.start_time.isoformat() if workflow.start_time else None,
                    "close_time": workflow.close_time.isoformat() if workflow.close_time else None,
                    "task_queue": workflow.task_queue,
                })

                if len(workflows) >= limit:
                    break

            logger.info(f"Listed {len(workflows)} workflows")
            return workflows

        except Exception as e:
            logger.error(f"Failed to list workflows: {e}", exc_info=True)
            raise
