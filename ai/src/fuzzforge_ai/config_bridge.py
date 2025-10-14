"""Bridge module providing access to the host CLI configuration manager."""
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.


try:
    from fuzzforge_cli.config import ProjectConfigManager as _ProjectConfigManager
except ImportError:  # pragma: no cover - used when CLI not available
    class _ProjectConfigManager:  # type: ignore[no-redef]
        """Fallback implementation that raises a helpful error."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "ProjectConfigManager is unavailable. Install the FuzzForge CLI "
                "package or supply a compatible configuration object."
            )

    def __getattr__(name):  # pragma: no cover - defensive
        raise ImportError("ProjectConfigManager unavailable")

ProjectConfigManager = _ProjectConfigManager

__all__ = ["ProjectConfigManager"]
