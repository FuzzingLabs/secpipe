from typing import TYPE_CHECKING, Literal

from fuzzforge_common.sandboxes.engines.base.configuration import AbstractFuzzForgeEngineConfiguration
from fuzzforge_common.sandboxes.engines.enumeration import FuzzForgeSandboxEngines
from fuzzforge_common.sandboxes.engines.podman.engine import Podman

if TYPE_CHECKING:
    from fuzzforge_common.sandboxes.engines.base.engine import AbstractFuzzForgeSandboxEngine


class PodmanConfiguration(AbstractFuzzForgeEngineConfiguration):
    """TODO."""

    #: TODO.
    kind: Literal[FuzzForgeSandboxEngines.PODMAN] = FuzzForgeSandboxEngines.PODMAN

    #: TODO.
    socket: str

    def into_engine(self) -> AbstractFuzzForgeSandboxEngine:
        """TODO."""
        return Podman(socket=self.socket)
