from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

from fuzzforge_common.sandboxes.engines.enumeration import (
    FuzzForgeSandboxEngines,
)

if TYPE_CHECKING:
    from fuzzforge_common.sandboxes.engines.base.engine import AbstractFuzzForgeSandboxEngine


class AbstractFuzzForgeEngineConfiguration(ABC, BaseModel):
    """TODO."""

    #: TODO.
    kind: FuzzForgeSandboxEngines

    @abstractmethod
    def into_engine(self) -> AbstractFuzzForgeSandboxEngine:
        """TODO."""
        message: str = f"method 'into_engine' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)
