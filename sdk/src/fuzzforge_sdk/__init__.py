"""
FuzzForge SDK - Python client for FuzzForge security testing platform

A comprehensive SDK for interacting with the FuzzForge API, providing
workflow management, real-time fuzzing monitoring, and SARIF findings retrieval.
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


from .client import FuzzForgeClient
from .models import (
    WorkflowSubmission,
    WorkflowMetadata,
    WorkflowListItem,
    WorkflowStatus,
    WorkflowFindings,
    FuzzingStats,
    CrashReport,
    RunSubmissionResponse,
)
from .exceptions import (
    FuzzForgeError,
    FuzzForgeHTTPError,
    WorkflowNotFoundError,
    RunNotFoundError,
    ValidationError,
)
from .testing import (
    WorkflowTester,
    TestResult,
    TestSummary,
    format_test_summary,
    DEFAULT_TEST_CONFIG,
)

__version__ = "0.7.3"
__all__ = [
    "FuzzForgeClient",
    "WorkflowSubmission",
    "WorkflowMetadata",
    "WorkflowListItem",
    "WorkflowStatus",
    "WorkflowFindings",
    "FuzzingStats",
    "CrashReport",
    "RunSubmissionResponse",
    "FuzzForgeError",
    "FuzzForgeHTTPError",
    "WorkflowNotFoundError",
    "RunNotFoundError",
    "ValidationError",
    "WorkflowTester",
    "TestResult",
    "TestSummary",
    "format_test_summary",
    "DEFAULT_TEST_CONFIG",
]


def main() -> None:
    """Entry point for the CLI (not implemented yet)"""
    print("FuzzForge SDK - Use as a library to interact with FuzzForge API")
