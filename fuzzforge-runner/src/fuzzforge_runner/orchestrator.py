"""FuzzForge Runner - Workflow orchestration without Temporal.

This module provides simplified workflow orchestration for sequential
module execution without requiring Temporal infrastructure.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from fuzzforge_runner.constants import FuzzForgeExecutionIdentifier
from fuzzforge_runner.exceptions import WorkflowExecutionError
from fuzzforge_runner.executor import ModuleExecutor

if TYPE_CHECKING:
    from fuzzforge_runner.settings import Settings
    from fuzzforge_runner.storage import LocalStorage
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow."""

    #: Module identifier to execute.
    module_identifier: str

    #: Optional configuration for the module.
    configuration: dict[str, Any] | None = None

    #: Step name/label for logging.
    name: str | None = None


@dataclass
class WorkflowDefinition:
    """Defines a workflow as a sequence of module executions."""

    #: Workflow name.
    name: str

    #: Ordered list of steps to execute.
    steps: list[WorkflowStep] = field(default_factory=list)

    #: Optional workflow description.
    description: str | None = None


@dataclass
class StepResult:
    """Result of a single workflow step execution."""

    #: Step index (0-based).
    step_index: int

    #: Module that was executed.
    module_identifier: str

    #: Path to the results archive.
    results_path: Path

    #: Execution identifier.
    execution_id: str

    #: Execution start time.
    started_at: datetime

    #: Execution end time.
    completed_at: datetime

    #: Whether execution was successful.
    success: bool = True

    #: Error message if failed.
    error: str | None = None


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution."""

    #: Workflow execution identifier.
    execution_id: str

    #: Workflow name.
    name: str

    #: Results for each step.
    steps: list[StepResult] = field(default_factory=list)

    #: Overall success status.
    success: bool = True

    #: Final results path (from last step).
    final_results_path: Path | None = None


class WorkflowOrchestrator:
    """Orchestrates sequential workflow execution.

    Executes workflow steps sequentially, passing output from each
    module as input to the next. No Temporal required.

    """

    #: Module executor instance.
    _executor: ModuleExecutor

    #: Storage backend.
    _storage: LocalStorage

    def __init__(self, executor: ModuleExecutor, storage: LocalStorage) -> None:
        """Initialize an instance of the class.

        :param executor: Module executor for running modules.
        :param storage: Storage backend for managing assets.

        """
        self._executor = executor
        self._storage = storage

    def _generate_execution_id(self) -> str:
        """Generate a unique execution identifier.

        :returns: UUID string for execution tracking.

        """
        return str(uuid4())

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        project_path: Path,
        initial_assets_path: Path | None = None,
    ) -> WorkflowResult:
        """Execute a workflow as a sequence of module executions.

        Each step receives the output of the previous step as input.
        The first step receives the initial assets.

        :param workflow: Workflow definition with steps to execute.
        :param project_path: Path to the project directory.
        :param initial_assets_path: Path to initial assets (optional).
        :returns: Workflow execution result.
        :raises WorkflowExecutionError: If workflow execution fails.

        """
        logger = get_logger()
        workflow_id = self._generate_execution_id()

        logger.info(
            "starting workflow execution",
            workflow=workflow.name,
            execution_id=workflow_id,
            steps=len(workflow.steps),
        )

        result = WorkflowResult(
            execution_id=workflow_id,
            name=workflow.name,
        )

        if not workflow.steps:
            logger.warning("workflow has no steps", workflow=workflow.name)
            return result

        # Track current assets path - starts with initial assets, then uses previous step output
        current_assets: Path | None = initial_assets_path

        # If no initial assets, try to get from project
        if current_assets is None:
            current_assets = self._storage.get_project_assets_path(project_path)

        try:
            for step_index, step in enumerate(workflow.steps):
                step_name = step.name or f"step-{step_index}"
                step_execution_id = self._generate_execution_id()

                logger.info(
                    "executing workflow step",
                    workflow=workflow.name,
                    step=step_name,
                    step_index=step_index,
                    module=step.module_identifier,
                    execution_id=step_execution_id,
                )

                started_at = datetime.now(UTC)

                try:
                    # Ensure we have assets for this step
                    if current_assets is None or not current_assets.exists():
                        if step_index == 0:
                            # First step with no assets - create empty archive
                            current_assets = self._storage.create_empty_assets_archive(project_path)
                        else:
                            message = f"No assets available for step {step_index}"
                            raise WorkflowExecutionError(message)

                    # Execute the module (inputs stored in .fuzzforge/inputs/)
                    results_path = await self._executor.execute(
                        module_identifier=step.module_identifier,
                        assets_path=current_assets,
                        configuration=step.configuration,
                        project_path=project_path,
                        execution_id=step_execution_id,
                    )

                    completed_at = datetime.now(UTC)

                    # Store results to persistent storage
                    stored_path = self._storage.store_execution_results(
                        project_path=project_path,
                        workflow_id=workflow_id,
                        step_index=step_index,
                        execution_id=step_execution_id,
                        results_path=results_path,
                    )

                    # Clean up temporary results archive after storing
                    try:
                        if results_path.exists() and results_path != stored_path:
                            results_path.unlink()
                    except Exception as cleanup_exc:
                        logger.warning("failed to clean up temporary results", path=str(results_path), error=str(cleanup_exc))

                    # Record step result with stored path
                    step_result = StepResult(
                        step_index=step_index,
                        module_identifier=step.module_identifier,
                        results_path=stored_path,
                        execution_id=step_execution_id,
                        started_at=started_at,
                        completed_at=completed_at,
                        success=True,
                    )
                    result.steps.append(step_result)

                    # Next step uses this step's output
                    current_assets = stored_path

                    logger.info(
                        "workflow step completed",
                        step=step_name,
                        step_index=step_index,
                        duration_seconds=(completed_at - started_at).total_seconds(),
                    )

                except Exception as exc:
                    completed_at = datetime.now(UTC)
                    error_msg = str(exc)

                    step_result = StepResult(
                        step_index=step_index,
                        module_identifier=step.module_identifier,
                        results_path=Path(),
                        execution_id=step_execution_id,
                        started_at=started_at,
                        completed_at=completed_at,
                        success=False,
                        error=error_msg,
                    )
                    result.steps.append(step_result)
                    result.success = False

                    logger.error(
                        "workflow step failed",
                        step=step_name,
                        step_index=step_index,
                        error=error_msg,
                    )

                    # Stop workflow on failure
                    break

            # Set final results path
            if result.steps and result.steps[-1].success:
                result.final_results_path = result.steps[-1].results_path

            logger.info(
                "workflow execution completed",
                workflow=workflow.name,
                execution_id=workflow_id,
                success=result.success,
                completed_steps=len([s for s in result.steps if s.success]),
                total_steps=len(workflow.steps),
            )

            return result

        except Exception as exc:
            message = f"Workflow execution failed: {exc}"
            logger.exception("workflow execution error", workflow=workflow.name)
            raise WorkflowExecutionError(message) from exc

    async def execute_single_module(
        self,
        module_identifier: str,
        project_path: Path,
        assets_path: Path | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> StepResult:
        """Execute a single module (convenience method).

        This is a simplified interface for executing a single module
        outside of a workflow context.

        :param module_identifier: Module to execute.
        :param project_path: Project directory path.
        :param assets_path: Optional path to input assets.
        :param configuration: Optional module configuration.
        :returns: Execution result.

        """
        workflow = WorkflowDefinition(
            name=f"single-{module_identifier}",
            steps=[
                WorkflowStep(
                    module_identifier=module_identifier,
                    configuration=configuration,
                    name="main",
                )
            ],
        )

        result = await self.execute_workflow(
            workflow=workflow,
            project_path=project_path,
            initial_assets_path=assets_path,
        )

        if result.steps:
            return result.steps[0]

        # Should not happen, but handle gracefully
        return StepResult(
            step_index=0,
            module_identifier=module_identifier,
            results_path=Path(),
            execution_id=result.execution_id,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            success=False,
            error="No step results produced",
        )
