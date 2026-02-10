"""Settings for the cargo-fuzzer module."""

from typing import Optional
from pydantic import model_validator
from fuzzforge_modules_sdk.api.models import FuzzForgeModulesSettingsBase


class Settings(FuzzForgeModulesSettingsBase):
    """Settings for the cargo-fuzzer module."""

    #: Maximum fuzzing duration in seconds (total across all targets)
    #: Set to 0 for infinite/continuous mode
    max_duration: int = 60
    
    #: Number of parallel fuzzing jobs
    jobs: int = 1
    
    #: Maximum length of generated inputs
    max_len: int = 4096
    
    #: Whether to use AddressSanitizer
    use_asan: bool = True
    
    #: Specific targets to fuzz (empty = all targets)
    targets: list[str] = []
    
    #: Single target to fuzz (convenience alias for targets)
    target: Optional[str] = None
    
    @model_validator(mode="after")
    def handle_single_target(self) -> "Settings":
        """Convert single target to targets list if provided."""
        if self.target and self.target not in self.targets:
            self.targets.append(self.target)
        return self
