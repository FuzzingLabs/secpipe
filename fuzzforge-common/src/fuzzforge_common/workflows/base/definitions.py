from enum import StrEnum
from typing import Literal

from fuzzforge_types import FuzzForgeWorkflowIdentifier  # noqa: TC002 (required by 'pydantic' at runtime)
from pydantic import BaseModel


class Base(BaseModel):
    """TODO."""


class FuzzForgeWorkflowSteps(StrEnum):
    """Workflow step types."""

    #: Execute a FuzzForge module
    RUN_FUZZFORGE_MODULE = "run-fuzzforge-module"


class FuzzForgeWorkflowStep(Base):
    """TODO."""

    #: The type of the workflow's step.
    kind: FuzzForgeWorkflowSteps


class RunFuzzForgeModule(FuzzForgeWorkflowStep):
    """Execute a FuzzForge module."""

    kind: Literal[FuzzForgeWorkflowSteps.RUN_FUZZFORGE_MODULE] = FuzzForgeWorkflowSteps.RUN_FUZZFORGE_MODULE
    #: The name of the module.
    module: str
    #: The container of the module.
    container: str


class FuzzForgeWorkflowDefinition(Base):
    """The definition of a FuzzForge workflow."""

    #: The author of the workflow.
    author: str
    #: The identifier of the workflow.
    identifier: FuzzForgeWorkflowIdentifier
    #: The name of the workflow.
    name: str
    #: The collection of steps that compose the workflow.
    steps: list[RunFuzzForgeModule]
