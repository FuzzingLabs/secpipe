"""SecPipe Common - Shared abstractions and implementations for SecPipe.

This package provides:
- Sandbox engine abstractions (Podman, Docker)
- Common exceptions

Example usage:
    from secpipe_common import (
        AbstractSecPipeSandboxEngine,
        ImageInfo,
        Podman,
        PodmanConfiguration,
    )
"""

from secpipe_common.exceptions import SecPipeError
from secpipe_common.sandboxes import (
    AbstractSecPipeEngineConfiguration,
    AbstractSecPipeSandboxEngine,
    Docker,
    DockerConfiguration,
    SecPipeSandboxEngines,
    ImageInfo,
    Podman,
    PodmanConfiguration,
)

__all__ = [
    "AbstractSecPipeEngineConfiguration",
    "AbstractSecPipeSandboxEngine",
    "Docker",
    "DockerConfiguration",
    "SecPipeError",
    "SecPipeSandboxEngines",
    "ImageInfo",
    "Podman",
    "PodmanConfiguration",
]
