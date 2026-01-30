"""
Android Security Analysis Modules

Modules for Android application security testing:
- JadxDecompiler: APK decompilation using Jadx
- MobSFScanner: Mobile security analysis using MobSF
- OpenGrepAndroid: Static analysis using OpenGrep/Semgrep with Android-specific rules
"""

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

from .jadx_decompiler import JadxDecompiler
from .opengrep_android import OpenGrepAndroid

# MobSF is optional (not available on ARM64 platform)
try:
    from .mobsf_scanner import MobSFScanner
    __all__ = ["JadxDecompiler", "MobSFScanner", "OpenGrepAndroid"]
except ImportError:
    # MobSF dependencies not available (e.g., ARM64 platform)
    MobSFScanner = None
    __all__ = ["JadxDecompiler", "OpenGrepAndroid"]
