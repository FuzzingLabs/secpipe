"""TODO."""

from datetime import datetime  # noqa: TC003

from pydantic import Field

from fuzzforge_types.bases import Base
from fuzzforge_types.definitions import FuzzForgeDefinitionIdentifier

type FuzzForgeModuleIdentifier = FuzzForgeDefinitionIdentifier


class FuzzForgeModule(Base):
    """TODO."""

    module_description: str = Field(
        description="The description of the module.",
    )
    module_identifier: FuzzForgeModuleIdentifier = Field(
        description="The identifier of the module.",
    )
    module_name: str = Field(
        description="The name of the module.",
    )
    created_at: datetime = Field(
        description="The creation date of the module.",
    )
    updated_at: datetime = Field(
        description="The latest modification date of the module.",
    )
