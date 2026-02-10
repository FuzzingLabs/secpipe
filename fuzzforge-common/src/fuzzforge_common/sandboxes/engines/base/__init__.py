"""Base engine abstractions."""

from fuzzforge_common.sandboxes.engines.base.configuration import (
    AbstractFuzzForgeEngineConfiguration,
)
from fuzzforge_common.sandboxes.engines.base.engine import (
    AbstractFuzzForgeSandboxEngine,
    ImageInfo,
)

__all__ = [
    "AbstractFuzzForgeEngineConfiguration",
    "AbstractFuzzForgeSandboxEngine",
    "ImageInfo",
]
