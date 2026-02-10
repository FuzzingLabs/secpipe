from typing import Any, Literal

from fuzzforge_types import (
    FuzzForgeExecutionIdentifier,  # noqa: TC002 (required by pydantic at runtime)
    FuzzForgeProjectIdentifier,  # noqa: TC002 (required by pydantic at runtime)
)

from fuzzforge_common.workflows.base.parameters import TemporalWorkflowParameters


class ExecuteFuzzForgeModuleParameters(TemporalWorkflowParameters):
    """Parameters for executing a single FuzzForge module workflow.

    Contains module execution configuration including container image,
    project context, and execution tracking identifiers.
    
    Supports workflow chaining where modules can be executed in sequence,
    with each module's output becoming the next module's input.

    """

    #: The identifier of this module execution.
    execution_identifier: FuzzForgeExecutionIdentifier

    #: The identifier/name of the module to execute.
    #: FIXME: Currently accepts both UUID (for registry lookups) and container names (e.g., "text-generator:0.0.1").
    #: This should be split into module_identifier (UUID) and container_image (string) in the future.
    module_identifier: str

    #: The identifier of the project this module execution belongs to.
    project_identifier: FuzzForgeProjectIdentifier

    #: Optional configuration dictionary for the module.
    #: Will be written to /data/input/config.json in the sandbox.
    module_configuration: dict[str, Any] | None = None

    # Workflow chaining fields

    #: The identifier of the parent workflow execution (if part of a multi-module workflow).
    #: For standalone module executions, this equals execution_identifier.
    workflow_execution_identifier: FuzzForgeExecutionIdentifier | None = None

    #: Position of this module in the workflow (0-based).
    #: 0 = first module (reads from project assets)
    #: N > 0 = subsequent module (reads from previous module's output)
    step_index: int = 0

    #: Execution identifier of the previous module in the workflow chain.
    #: None for first module (step_index=0).
    #: Used to locate previous module's output in storage.
    previous_step_execution_identifier: FuzzForgeExecutionIdentifier | None = None


class WorkflowStep(TemporalWorkflowParameters):
    """A step in a workflow - a module execution.
    
    Steps are executed sequentially in a workflow. Each step runs a containerized module.
    
    Examples:
        # Module step
        WorkflowStep(
            step_index=0,
            step_type="module",
            module_identifier="text-generator:0.0.1"
        )

    """

    #: Position of this step in the workflow (0-based)
    step_index: int

    #: Type of step: "module" (bridges are also modules now)
    step_type: Literal["module"]

    #: Module identifier (container image name like "text-generator:0.0.1")
    #: Required if step_type="module"
    module_identifier: str | None = None

    #: Optional module configuration
    module_configuration: dict[str, Any] | None = None
