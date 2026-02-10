"""Definition types for FuzzForge.

This module defines the base types and enums for FuzzForge definitions,
including modules and workflows.

"""

from enum import StrEnum

from pydantic import UUID7


class FuzzForgeDefinitionTypes(StrEnum):
    """Kind of FuzzForge definition.

    Discriminator enum used to distinguish between module and workflow definitions
    in the unified definitions table.

    """

    MODULE_DEFINITION = "module"
    WORKFLOW_DEFINITION = "workflow"


# Type aliases for definition identifiers
type FuzzForgeDefinitionIdentifier = UUID7
