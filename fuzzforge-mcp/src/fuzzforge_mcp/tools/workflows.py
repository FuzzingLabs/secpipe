"""Workflow tools for FuzzForge MCP."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fuzzforge_runner.orchestrator import WorkflowDefinition, WorkflowStep

from fuzzforge_mcp.dependencies import get_project_path, get_runner

if TYPE_CHECKING:
    from fuzzforge_runner import Runner
    from fuzzforge_runner.orchestrator import WorkflowResult


mcp: FastMCP = FastMCP()


@mcp.tool
async def execute_workflow(
    workflow_name: str,
    steps: list[dict[str, Any]],
    initial_assets_path: str | None = None,
) -> dict[str, Any]:
    """Execute a workflow consisting of multiple module steps.

    A workflow chains multiple modules together, passing the output of each
    module as input to the next. This enables complex pipelines.

    :param workflow_name: Name for this workflow execution.
    :param steps: List of step definitions, each with "module" and optional "configuration".
    :param initial_assets_path: Optional path to initial assets for the first step.
    :return: Workflow execution result including status of each step.

    Example steps format:
        [
            {"module": "module-a", "configuration": {"key": "value"}},
            {"module": "module-b", "configuration": {}},
            {"module": "module-c"}
        ]

    """
    runner: Runner = get_runner()
    project_path: Path = get_project_path()

    try:
        # Convert step dicts to WorkflowStep objects
        workflow_steps = [
            WorkflowStep(
                module_identifier=step["module"],
                configuration=step.get("configuration"),
                name=step.get("name", f"step-{i}"),
            )
            for i, step in enumerate(steps)
        ]

        workflow = WorkflowDefinition(
            name=workflow_name,
            steps=workflow_steps,
        )

        result: WorkflowResult = await runner.execute_workflow(
            workflow=workflow,
            project_path=project_path,
            initial_assets_path=Path(initial_assets_path) if initial_assets_path else None,
        )

        return {
            "success": result.success,
            "execution_id": result.execution_id,
            "workflow_name": result.name,
            "final_results_path": str(result.final_results_path) if result.final_results_path else None,
            "steps": [
                {
                    "step_index": step.step_index,
                    "module": step.module_identifier,
                    "success": step.success,
                    "execution_id": step.execution_id,
                    "results_path": str(step.results_path) if step.results_path else None,
                    "error": step.error,
                }
                for step in result.steps
            ],
        }

    except Exception as exception:
        message: str = f"Workflow execution failed: {exception}"
        raise ToolError(message) from exception

