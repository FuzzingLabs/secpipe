from typing import TYPE_CHECKING, Literal

from secpipe_common.sandboxes.engines.base.configuration import AbstractSecPipeEngineConfiguration
from secpipe_common.sandboxes.engines.enumeration import SecPipeSandboxEngines
from secpipe_common.sandboxes.engines.podman.engine import Podman

if TYPE_CHECKING:
    from secpipe_common.sandboxes.engines.base.engine import AbstractSecPipeSandboxEngine


class PodmanConfiguration(AbstractSecPipeEngineConfiguration):
    """TODO."""

    #: TODO.
    kind: Literal[SecPipeSandboxEngines.PODMAN] = SecPipeSandboxEngines.PODMAN

    #: TODO.
    socket: str

    def into_engine(self) -> AbstractSecPipeSandboxEngine:
        """TODO."""
        return Podman(socket=self.socket)
