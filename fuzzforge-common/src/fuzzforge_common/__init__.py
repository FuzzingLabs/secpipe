"""FuzzForge Common - Shared abstractions and implementations for FuzzForge.

This package provides:
- Sandbox engine abstractions (Podman, Docker)
- Common exceptions

Example usage:
    from fuzzforge_common import (
        AbstractFuzzForgeSandboxEngine,
        ImageInfo,
        Podman,
        PodmanConfiguration,
    )
"""

from fuzzforge_common.exceptions import FuzzForgeError
from fuzzforge_common.sandboxes import (
    AbstractFuzzForgeEngineConfiguration,
    AbstractFuzzForgeSandboxEngine,
    Docker,
    DockerConfiguration,
    FuzzForgeSandboxEngines,
    ImageInfo,
    Podman,
    PodmanConfiguration,
)

__all__ = [
    "AbstractFuzzForgeEngineConfiguration",
    "AbstractFuzzForgeSandboxEngine",
    "Docker",
    "DockerConfiguration",
    "FuzzForgeError",
    "FuzzForgeSandboxEngines",
    "ImageInfo",
    "Podman",
    "PodmanConfiguration",
]
