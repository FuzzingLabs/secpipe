"""Settings for rust-analyzer module."""

from fuzzforge_modules_sdk.api.models import FuzzForgeModulesSettingsBase


class Settings(FuzzForgeModulesSettingsBase):
    """Settings for the rust-analyzer module."""

    #: Whether to run cargo-audit for CVE detection.
    run_audit: bool = True

    #: Whether to run cargo-geiger for unsafe detection.
    run_geiger: bool = True

    #: Maximum depth for dependency analysis.
    max_depth: int = 3
