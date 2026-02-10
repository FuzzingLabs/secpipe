from fuzzforge_types import (
    FuzzForgeExecutionIdentifier,  # noqa: TC002 (required by pydantic at runtime)
    FuzzForgeProjectIdentifier,  # noqa: TC002 (required by pydantic at runtime)
)

from fuzzforge_common.workflows.base.definitions import (
    FuzzForgeWorkflowDefinition,  # noqa: TC001 (required by pydantic at runtime)
)
from fuzzforge_common.workflows.base.parameters import TemporalWorkflowParameters


class ExecuteFuzzForgeWorkflowParameters(TemporalWorkflowParameters):
    """Parameters for the default FuzzForge workflow orchestration.

    Contains workflow definition and execution tracking identifiers
    for coordinating multi-module workflows.

    """

    #: UUID7 identifier of this specific workflow execution.
    execution_identifier: FuzzForgeExecutionIdentifier

    #: UUID7 identifier of the project this execution belongs to.
    project_identifier: FuzzForgeProjectIdentifier

    #: The definition of the FuzzForge workflow to run.
    workflow_definition: FuzzForgeWorkflowDefinition
