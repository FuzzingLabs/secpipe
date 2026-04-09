"""Base engine abstractions."""

from secpipe_common.sandboxes.engines.base.configuration import (
    AbstractSecPipeEngineConfiguration,
)
from secpipe_common.sandboxes.engines.base.engine import (
    AbstractSecPipeSandboxEngine,
    ImageInfo,
)

__all__ = [
    "AbstractSecPipeEngineConfiguration",
    "AbstractSecPipeSandboxEngine",
    "ImageInfo",
]
