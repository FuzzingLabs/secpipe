from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

from secpipe_common.sandboxes.engines.enumeration import (
    SecPipeSandboxEngines,
)

if TYPE_CHECKING:
    from secpipe_common.sandboxes.engines.base.engine import AbstractSecPipeSandboxEngine


class AbstractSecPipeEngineConfiguration(ABC, BaseModel):
    """TODO."""

    #: TODO.
    kind: SecPipeSandboxEngines

    @abstractmethod
    def into_engine(self) -> AbstractSecPipeSandboxEngine:
        """TODO."""
        message: str = f"method 'into_engine' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)
