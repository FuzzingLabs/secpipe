"""TODO."""

from datetime import datetime  # noqa: TC003
from enum import StrEnum

from pydantic import UUID7, Field

from fuzzforge_types.bases import Base
from fuzzforge_types.definitions import FuzzForgeDefinitionIdentifier, FuzzForgeDefinitionTypes  # noqa: TC001
from fuzzforge_types.identifiers import FuzzForgeProjectIdentifier  # noqa: TC001


class FuzzForgeExecutionStatus(StrEnum):
    """TODO."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


class FuzzForgeExecutionError(StrEnum):
    """TODO."""

    GENERIC_ERROR = "GENERIC_ERROR"


class FuzzForgeExecutionIncludeFilter(StrEnum):
    """Filter for including specific execution types when listing.

    Used to filter executions by their definition kind (module or workflow).
    This filter is required when listing executions to ensure explicit intent.

    """

    ALL = "all"
    MODULES = "modules"
    WORKFLOWS = "workflows"


# Type alias for unified execution identifiers
type FuzzForgeExecutionIdentifier = UUID7


class FuzzForgeExecution(Base):
    """DTO for unified execution data.

    Represents both module and workflow executions in a single model.
    The definition_kind field discriminates between the two types.

    """

    execution_identifier: FuzzForgeExecutionIdentifier = Field(
        description="The identifier of this execution.",
    )
    execution_status: FuzzForgeExecutionStatus = Field(
        description="The current status of the execution.",
    )
    execution_error: FuzzForgeExecutionError | None = Field(
        description="The error associated with the execution, if any.",
    )
    project_identifier: FuzzForgeProjectIdentifier = Field(
        description="The identifier of the project this execution belongs to.",
    )
    definition_identifier: FuzzForgeDefinitionIdentifier = Field(
        description="The identifier of the definition (module or workflow) being executed.",
    )
    definition_kind: FuzzForgeDefinitionTypes = Field(
        description="The kind of definition being executed (module or workflow).",
    )
    created_at: datetime = Field(
        description="The creation date of the execution.",
    )
    updated_at: datetime = Field(
        description="The latest modification date of the execution.",
    )
