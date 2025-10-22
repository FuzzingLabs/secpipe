"""
FuzzForge Vertical Worker: Secret Detection

This worker:
1. Discovers workflows for the 'secrets' vertical from mounted toolbox
2. Dynamically imports and registers workflow classes
3. Connects to Temporal and processes tasks
4. Handles activities for target download/upload from MinIO
"""

import asyncio
import importlib
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import List, Any

import yaml
from temporalio.client import Client
from temporalio.worker import Worker

# Add toolbox to path for workflow and activity imports
sys.path.insert(0, '/app/toolbox')

# Import common storage activities
from toolbox.common.storage_activities import (
    get_target_activity,
    cleanup_cache_activity,
    upload_results_activity
)

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def discover_workflows(vertical: str) -> List[Any]:
    """
    Discover workflows for this vertical from mounted toolbox.

    Args:
        vertical: The vertical name (e.g., 'secrets', 'python', 'web')

    Returns:
        List of workflow classes decorated with @workflow.defn
    """
    workflows = []
    toolbox_path = Path("/app/toolbox/workflows")

    if not toolbox_path.exists():
        logger.warning(f"Toolbox path does not exist: {toolbox_path}")
        return workflows

    logger.info(f"Scanning for workflows in: {toolbox_path}")

    for workflow_dir in toolbox_path.iterdir():
        if not workflow_dir.is_dir():
            continue

        # Skip special directories
        if workflow_dir.name.startswith('.') or workflow_dir.name == '__pycache__':
            continue

        metadata_file = workflow_dir / "metadata.yaml"
        if not metadata_file.exists():
            logger.debug(f"No metadata.yaml in {workflow_dir.name}, skipping")
            continue

        try:
            # Parse metadata
            with open(metadata_file) as f:
                metadata = yaml.safe_load(f)

            # Check if workflow is for this vertical
            workflow_vertical = metadata.get("vertical")
            if workflow_vertical != vertical:
                logger.debug(
                    f"Workflow {workflow_dir.name} is for vertical '{workflow_vertical}', "
                    f"not '{vertical}', skipping"
                )
                continue

            # Check if workflow.py exists
            workflow_file = workflow_dir / "workflow.py"
            if not workflow_file.exists():
                logger.warning(
                    f"Workflow {workflow_dir.name} has metadata but no workflow.py, skipping"
                )
                continue

            # Dynamically import workflow module
            module_name = f"toolbox.workflows.{workflow_dir.name}.workflow"
            logger.info(f"Importing workflow module: {module_name}")

            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                logger.error(
                    f"Failed to import workflow module {module_name}: {e}",
                    exc_info=True
                )
                continue

            # Find @workflow.defn decorated classes
            found_workflows = False
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if class has Temporal workflow definition
                if hasattr(obj, '__temporal_workflow_definition'):
                    workflows.append(obj)
                    found_workflows = True
                    logger.info(
                        f"✓ Discovered workflow: {name} from {workflow_dir.name} "
                        f"(vertical: {vertical})"
                    )

            if not found_workflows:
                logger.warning(
                    f"Workflow {workflow_dir.name} has no @workflow.defn decorated classes"
                )

        except Exception as e:
            logger.error(
                f"Error processing workflow {workflow_dir.name}: {e}",
                exc_info=True
            )
            continue

    logger.info(f"Discovered {len(workflows)} workflows for vertical '{vertical}'")
    return workflows


async def discover_activities(workflows_dir: Path) -> List[Any]:
    """
    Discover activities from workflow directories.

    Looks for activities.py files alongside workflow.py in each workflow directory.

    Args:
        workflows_dir: Path to workflows directory

    Returns:
        List of activity functions decorated with @activity.defn
    """
    activities = []

    if not workflows_dir.exists():
        logger.warning(f"Workflows directory does not exist: {workflows_dir}")
        return activities

    logger.info(f"Scanning for workflow activities in: {workflows_dir}")

    for workflow_dir in workflows_dir.iterdir():
        if not workflow_dir.is_dir():
            continue

        # Skip special directories
        if workflow_dir.name.startswith('.') or workflow_dir.name == '__pycache__':
            continue

        # Check if activities.py exists
        activities_file = workflow_dir / "activities.py"
        if not activities_file.exists():
            logger.debug(f"No activities.py in {workflow_dir.name}, skipping")
            continue

        try:
            # Dynamically import activities module
            module_name = f"toolbox.workflows.{workflow_dir.name}.activities"
            logger.info(f"Importing activities module: {module_name}")

            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                logger.error(
                    f"Failed to import activities module {module_name}: {e}",
                    exc_info=True
                )
                continue

            # Find @activity.defn decorated functions
            found_activities = False
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                # Check if function has Temporal activity definition
                if hasattr(obj, '__temporal_activity_definition'):
                    activities.append(obj)
                    found_activities = True
                    logger.info(
                        f"✓ Discovered activity: {name} from {workflow_dir.name}"
                    )

            if not found_activities:
                logger.warning(
                    f"Workflow {workflow_dir.name} has activities.py but no @activity.defn decorated functions"
                )

        except Exception as e:
            logger.error(
                f"Error processing activities from {workflow_dir.name}: {e}",
                exc_info=True
            )
            continue

    logger.info(f"Discovered {len(activities)} workflow-specific activities")
    return activities


async def main():
    """Main worker entry point"""
    # Get configuration from environment
    vertical = os.getenv("WORKER_VERTICAL", "secrets")
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("WORKER_TASK_QUEUE", f"{vertical}-queue")
    max_concurrent_activities = int(os.getenv("MAX_CONCURRENT_ACTIVITIES", "5"))

    logger.info("=" * 60)
    logger.info(f"FuzzForge Vertical Worker: {vertical}")
    logger.info("=" * 60)
    logger.info(f"Temporal Address: {temporal_address}")
    logger.info(f"Temporal Namespace: {temporal_namespace}")
    logger.info(f"Task Queue: {task_queue}")
    logger.info(f"Max Concurrent Activities: {max_concurrent_activities}")
    logger.info("=" * 60)

    # Discover workflows for this vertical
    logger.info(f"Discovering workflows for vertical: {vertical}")
    workflows = await discover_workflows(vertical)

    if not workflows:
        logger.error(f"No workflows found for vertical: {vertical}")
        logger.error("Worker cannot start without workflows. Exiting...")
        sys.exit(1)

    # Discover activities from workflow directories
    logger.info("Discovering workflow-specific activities...")
    workflows_dir = Path("/app/toolbox/workflows")
    workflow_activities = await discover_activities(workflows_dir)

    # Combine common storage activities with workflow-specific activities
    activities = [
        get_target_activity,
        cleanup_cache_activity,
        upload_results_activity
    ] + workflow_activities

    logger.info(
        f"Total activities registered: {len(activities)} "
        f"(3 common + {len(workflow_activities)} workflow-specific)"
    )

    # Connect to Temporal
    logger.info(f"Connecting to Temporal at {temporal_address}...")
    try:
        client = await Client.connect(
            temporal_address,
            namespace=temporal_namespace
        )
        logger.info("✓ Connected to Temporal successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Temporal: {e}", exc_info=True)
        sys.exit(1)

    # Create worker with discovered workflows and activities
    logger.info(f"Creating worker on task queue: {task_queue}")

    try:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            max_concurrent_activities=max_concurrent_activities
        )
        logger.info("✓ Worker created successfully")
    except Exception as e:
        logger.error(f"Failed to create worker: {e}", exc_info=True)
        sys.exit(1)

    # Start worker
    logger.info("=" * 60)
    logger.info(f"🚀 Worker started for vertical '{vertical}'")
    logger.info(f"📦 Registered {len(workflows)} workflows")
    logger.info(f"⚙️  Registered {len(activities)} activities")
    logger.info(f"📨 Listening on task queue: {task_queue}")
    logger.info("=" * 60)
    logger.info("Worker is ready to process tasks...")

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Shutting down worker (keyboard interrupt)...")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
