from typing import TYPE_CHECKING, Literal

from fuzzforge_common.sandboxes.engines.base.configuration import AbstractFuzzForgeEngineConfiguration
from fuzzforge_common.sandboxes.engines.docker.engine import Docker
from fuzzforge_common.sandboxes.engines.enumeration import FuzzForgeSandboxEngines

if TYPE_CHECKING:
    from fuzzforge_common.sandboxes.engines.base.engine import AbstractFuzzForgeSandboxEngine


class DockerConfiguration(AbstractFuzzForgeEngineConfiguration):
    """TODO."""

    #: TODO.
    kind: Literal[FuzzForgeSandboxEngines.DOCKER] = FuzzForgeSandboxEngines.DOCKER

    #: TODO.
    socket: str

    def into_engine(self) -> AbstractFuzzForgeSandboxEngine:
        """TODO."""
        return Docker(socket=self.socket)
