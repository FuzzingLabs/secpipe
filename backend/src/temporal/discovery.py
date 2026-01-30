"""
Workflow Discovery for Temporal

Discovers workflows from the toolbox/workflows directory
and provides metadata about available workflows.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class WorkflowInfo(BaseModel):
    """Information about a discovered workflow"""
    name: str = Field(..., description="Workflow name")
    path: Path = Field(..., description="Path to workflow directory")
    workflow_file: Path = Field(..., description="Path to workflow.py file")
    metadata: Dict[str, Any] = Field(..., description="Workflow metadata from YAML")
    workflow_type: str = Field(..., description="Workflow class name")
    vertical: str = Field(..., description="Vertical (worker type) for this workflow")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class WorkflowDiscovery:
    """
    Discovers workflows from the filesystem.

    Scans toolbox/workflows/ for directories containing:
    - metadata.yaml (required)
    - workflow.py (required)

    Each workflow declares its vertical (rust, android, web, etc.)
    which determines which worker pool will execute it.
    """

    def __init__(self, workflows_dir: Path):
        """
        Initialize workflow discovery.

        Args:
            workflows_dir: Path to the workflows directory
        """
        self.workflows_dir = workflows_dir
        if not self.workflows_dir.exists():
            self.workflows_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created workflows directory: {self.workflows_dir}")

    async def discover_workflows(self) -> Dict[str, WorkflowInfo]:
        """
        Discover workflows by scanning the workflows directory.

        Returns:
            Dictionary mapping workflow names to their information
        """
        workflows = {}

        logger.info(f"Scanning for workflows in: {self.workflows_dir}")

        for workflow_dir in self.workflows_dir.iterdir():
            if not workflow_dir.is_dir():
                continue

            # Skip special directories
            if workflow_dir.name.startswith('.') or workflow_dir.name == '__pycache__':
                continue

            metadata_file = workflow_dir / "metadata.yaml"
            if not metadata_file.exists():
                logger.debug(f"No metadata.yaml in {workflow_dir.name}, skipping")
                continue

            workflow_file = workflow_dir / "workflow.py"
            if not workflow_file.exists():
                logger.warning(
                    f"Workflow {workflow_dir.name} has metadata but no workflow.py, skipping"
                )
                continue

            try:
                # Parse metadata
                with open(metadata_file) as f:
                    metadata = yaml.safe_load(f)

                # Validate required fields
                if 'name' not in metadata:
                    logger.warning(f"Workflow {workflow_dir.name} metadata missing 'name' field")
                    metadata['name'] = workflow_dir.name

                if 'vertical' not in metadata:
                    logger.warning(
                        f"Workflow {workflow_dir.name} metadata missing 'vertical' field"
                    )
                    continue

                # Infer workflow class name from metadata or use convention
                workflow_type = metadata.get('workflow_class')
                if not workflow_type:
                    # Convention: convert snake_case to PascalCase + Workflow
                    # e.g., rust_test -> RustTestWorkflow
                    parts = workflow_dir.name.split('_')
                    workflow_type = ''.join(part.capitalize() for part in parts) + 'Workflow'

                # Create workflow info
                info = WorkflowInfo(
                    name=metadata['name'],
                    path=workflow_dir,
                    workflow_file=workflow_file,
                    metadata=metadata,
                    workflow_type=workflow_type,
                    vertical=metadata['vertical']
                )

                workflows[info.name] = info
                logger.info(
                    f"✓ Discovered workflow: {info.name} "
                    f"(vertical: {info.vertical}, class: {info.workflow_type})"
                )

            except Exception as e:
                logger.error(
                    f"Error discovering workflow {workflow_dir.name}: {e}",
                    exc_info=True
                )
                continue

        logger.info(f"Discovered {len(workflows)} workflows")
        return workflows

    def get_workflows_by_vertical(
        self,
        workflows: Dict[str, WorkflowInfo],
        vertical: str
    ) -> Dict[str, WorkflowInfo]:
        """
        Filter workflows by vertical.

        Args:
            workflows: All discovered workflows
            vertical: Vertical name to filter by

        Returns:
            Filtered workflows dictionary
        """
        return {
            name: info
            for name, info in workflows.items()
            if info.vertical == vertical
        }

    def get_available_verticals(self, workflows: Dict[str, WorkflowInfo]) -> list[str]:
        """
        Get list of all verticals from discovered workflows.

        Args:
            workflows: All discovered workflows

        Returns:
            List of unique vertical names
        """
        return list(set(info.vertical for info in workflows.values()))

    @staticmethod
    def get_metadata_schema() -> Dict[str, Any]:
        """
        Get the JSON schema for workflow metadata.

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "required": ["name", "version", "description", "author", "vertical", "parameters"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Workflow name"
                },
                "version": {
                    "type": "string",
                    "pattern": "^\\d+\\.\\d+\\.\\d+$",
                    "description": "Semantic version (x.y.z)"
                },
                "vertical": {
                    "type": "string",
                    "description": "Vertical worker type (rust, android, web, etc.)"
                },
                "description": {
                    "type": "string",
                    "description": "Workflow description"
                },
                "author": {
                    "type": "string",
                    "description": "Workflow author"
                },
                "category": {
                    "type": "string",
                    "enum": ["comprehensive", "specialized", "fuzzing", "focused"],
                    "description": "Workflow category"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Workflow tags for categorization"
                },
                "requirements": {
                    "type": "object",
                    "required": ["tools", "resources"],
                    "properties": {
                        "tools": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required security tools"
                        },
                        "resources": {
                            "type": "object",
                            "required": ["memory", "cpu", "timeout"],
                            "properties": {
                                "memory": {
                                    "type": "string",
                                    "pattern": "^\\d+[GMK]i$",
                                    "description": "Memory limit (e.g., 1Gi, 512Mi)"
                                },
                                "cpu": {
                                    "type": "string",
                                    "pattern": "^\\d+m?$",
                                    "description": "CPU limit (e.g., 1000m, 2)"
                                },
                                "timeout": {
                                    "type": "integer",
                                    "minimum": 60,
                                    "maximum": 7200,
                                    "description": "Workflow timeout in seconds"
                                }
                            }
                        }
                    }
                },
                "parameters": {
                    "type": "object",
                    "description": "Workflow parameters schema"
                },
                "default_parameters": {
                    "type": "object",
                    "description": "Default parameter values"
                },
                "required_modules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required module names"
                }
            }
        }
