"""FuzzForge Common - Shared abstractions and implementations for FuzzForge.

This package provides:
- Sandbox engine abstractions (Podman, Docker)
- Storage abstractions (S3) - requires 'storage' extra
- Common exceptions

Example usage:
    from fuzzforge_common import (
        AbstractFuzzForgeSandboxEngine,
        ImageInfo,
        Podman,
        PodmanConfiguration,
    )

    # For storage (requires boto3):
    from fuzzforge_common.storage import Storage
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

# Storage exceptions are always available (no boto3 required)
from fuzzforge_common.storage.exceptions import (
    FuzzForgeStorageError,
    StorageConnectionError,
    StorageDownloadError,
    StorageUploadError,
)

__all__ = [
    "AbstractFuzzForgeEngineConfiguration",
    "AbstractFuzzForgeSandboxEngine",
    "Docker",
    "DockerConfiguration",
    "FuzzForgeError",
    "FuzzForgeSandboxEngines",
    "FuzzForgeStorageError",
    "ImageInfo",
    "Podman",
    "PodmanConfiguration",
    "StorageConnectionError",
    "StorageDownloadError",
    "StorageUploadError",
]
