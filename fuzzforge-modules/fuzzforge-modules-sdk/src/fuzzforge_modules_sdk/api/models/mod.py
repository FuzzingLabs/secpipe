"""Core module models for FuzzForge modules SDK.

This module contains the base classes for module settings, inputs, and resources.
These are compatible with the fuzzforge-core SDK structure.
"""

from enum import StrEnum
from pathlib import Path  # noqa: TC003 (required by pydantic at runtime)
from typing import TypeVar

from pydantic import BaseModel, ConfigDict


class Base(BaseModel):
    """Base model for all FuzzForge module types."""

    model_config = ConfigDict(extra="forbid")


class FuzzForgeModulesSettingsBase(Base):
    """Base class for module settings."""


FuzzForgeModulesSettingsType = TypeVar("FuzzForgeModulesSettingsType", bound=FuzzForgeModulesSettingsBase)


class FuzzForgeModuleResources(StrEnum):
    """Enumeration of resource types."""

    #: The type of the resource is unknown or irrelevant.
    UNKNOWN = "unknown"


class FuzzForgeModuleResource(Base):
    """A resource provided to a module as input."""

    #: The description of the resource.
    description: str
    #: The type of the resource.
    kind: FuzzForgeModuleResources
    #: The name of the resource.
    name: str
    #: The path of the resource on disk.
    path: Path


class FuzzForgeModuleInputBase[FuzzForgeModulesSettingsType: FuzzForgeModulesSettingsBase](Base):
    """The (standardized) input of a FuzzForge module."""

    #: The collection of resources given to the module as inputs.
    resources: list[FuzzForgeModuleResource]
    #: The settings of the module.
    settings: FuzzForgeModulesSettingsType
