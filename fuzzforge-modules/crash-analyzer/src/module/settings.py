"""Settings for the crash-analyzer module."""

from fuzzforge_modules_sdk.api.models import FuzzForgeModulesSettingsBase


class Settings(FuzzForgeModulesSettingsBase):
    """Settings for the crash-analyzer module."""

    #: Whether to reproduce crashes for stack traces
    reproduce_crashes: bool = True
    
    #: Timeout for reproducing each crash (seconds)
    reproduce_timeout: int = 30
    
    #: Whether to deduplicate crashes
    deduplicate: bool = True
