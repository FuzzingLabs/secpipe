"""TODO."""

from datetime import datetime  # noqa: TC003

from pydantic import Field

from fuzzforge_types.bases import Base
from fuzzforge_types.definitions import FuzzForgeDefinitionIdentifier

type FuzzForgeWorkflowIdentifier = FuzzForgeDefinitionIdentifier


class FuzzForgeWorkflow(Base):
    """TODO."""

    workflow_description: str = Field(
        description="The description of the workflow.",
    )
    workflow_identifier: FuzzForgeWorkflowIdentifier = Field(
        description="The identifier of the workflow.",
    )
    workflow_name: str = Field(
        description="The name of the workflow.",
    )
    created_at: datetime = Field(
        description="The creation date of the workflow.",
    )
    updated_at: datetime = Field(
        description="The latest modification date of the workflow.",
    )
