"""TODO."""

from datetime import datetime  # noqa: TC003

from pydantic import Field

from fuzzforge_types.bases import Base
from fuzzforge_types.executions import FuzzForgeExecution  # noqa: TC001
from fuzzforge_types.identifiers import FuzzForgeProjectIdentifier  # noqa: TC001


class FuzzForgeProject(Base):
    """TODO."""

    project_description: str = Field(
        description="The description of the project.",
    )
    project_identifier: FuzzForgeProjectIdentifier = Field(
        description="The identifier of the project.",
    )
    project_name: str = Field(
        description="The name of the project.",
    )
    created_at: datetime = Field(
        description="The creation date of the project.",
    )
    updated_at: datetime = Field(
        description="The latest modification date of the project.",
    )

    executions: list[FuzzForgeExecution] | None = Field(
        default=None,
        description="The module and workflow executions associated with the project.",
    )
