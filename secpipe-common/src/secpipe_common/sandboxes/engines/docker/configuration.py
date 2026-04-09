from typing import TYPE_CHECKING, Literal

from secpipe_common.sandboxes.engines.base.configuration import AbstractSecPipeEngineConfiguration
from secpipe_common.sandboxes.engines.docker.engine import Docker
from secpipe_common.sandboxes.engines.enumeration import SecPipeSandboxEngines

if TYPE_CHECKING:
    from secpipe_common.sandboxes.engines.base.engine import AbstractSecPipeSandboxEngine


class DockerConfiguration(AbstractSecPipeEngineConfiguration):
    """TODO."""

    #: TODO.
    kind: Literal[SecPipeSandboxEngines.DOCKER] = SecPipeSandboxEngines.DOCKER

    #: TODO.
    socket: str

    def into_engine(self) -> AbstractSecPipeSandboxEngine:
        """TODO."""
        return Docker(socket=self.socket)
