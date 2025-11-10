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
"""Fixtures used across tests."""

import sys
from collections.abc import Callable
from pathlib import Path
from types import CoroutineType
from typing import Any

import pytest
from modules.analyzer.security_analyzer import SecurityAnalyzer
from modules.fuzzer.atheris_fuzzer import AtherisFuzzer
from modules.fuzzer.cargo_fuzzer import CargoFuzzer
from modules.scanner.file_scanner import FileScanner

# Ensure project root is on sys.path so `src` is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Add toolbox to path for module imports
TOOLBOX = ROOT / "toolbox"
if str(TOOLBOX) not in sys.path:
    sys.path.insert(0, str(TOOLBOX))


# ============================================================================
# Workspace Fixtures
# ============================================================================


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def python_test_workspace(temp_workspace: Path) -> Path:
    """Create a Python test workspace with sample files."""
    # Create a simple Python project structure
    (temp_workspace / "main.py").write_text("""
def process_data(data):
    # Intentional bug: no bounds checking
    return data[0:100]

def divide(a, b):
    # Division by zero vulnerability
    return a / b
""")

    (temp_workspace / "config.py").write_text("""
# Hardcoded secrets for testing
API_KEY = "sk_test_1234567890abcdef"
DATABASE_URL = "postgresql://admin:password123@localhost/db"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
""")

    return temp_workspace


@pytest.fixture
def rust_test_workspace(temp_workspace: Path) -> Path:
    """Create a Rust test workspace with fuzz targets."""
    # Create Cargo.toml
    (temp_workspace / "Cargo.toml").write_text("""[package]
name = "test_project"
version = "0.1.0"
edition = "2021"

[dependencies]
""")

    # Create src/lib.rs
    src_dir = temp_workspace / "src"
    src_dir.mkdir()
    (src_dir / "lib.rs").write_text("""
pub fn process_buffer(data: &[u8]) -> Vec<u8> {
    if data.len() < 4 {
        return Vec::new();
    }

    // Vulnerability: bounds checking issue
    let size = data[0] as usize;
    let mut result = Vec::new();
    for i in 0..size {
        result.push(data[i]);
    }
    result
}
""")

    # Create fuzz directory structure
    fuzz_dir = temp_workspace / "fuzz"
    fuzz_dir.mkdir()

    (fuzz_dir / "Cargo.toml").write_text("""[package]
name = "test_project-fuzz"
version = "0.0.0"
edition = "2021"

[dependencies]
libfuzzer-sys = "0.4"

[dependencies.test_project]
path = ".."

[[bin]]
name = "fuzz_target_1"
path = "fuzz_targets/fuzz_target_1.rs"
""")

    fuzz_targets_dir = fuzz_dir / "fuzz_targets"
    fuzz_targets_dir.mkdir()

    (fuzz_targets_dir / "fuzz_target_1.rs").write_text("""#![no_main]
use libfuzzer_sys::fuzz_target;
use test_project::process_buffer;

fuzz_target!(|data: &[u8]| {
    let _ = process_buffer(data);
});
""")

    return temp_workspace


# ============================================================================
# Module Configuration Fixtures
# ============================================================================


@pytest.fixture
def atheris_config() -> dict[str, Any]:
    """Return default Atheris fuzzer configuration."""
    return {
        "target_file": "auto-discover",
        "max_iterations": 1000,
        "timeout_seconds": 10,
        "corpus_dir": None,
    }


@pytest.fixture
def cargo_fuzz_config() -> dict[str, Any]:
    """Return default cargo-fuzz configuration."""
    return {
        "target_name": None,
        "max_iterations": 1000,
        "timeout_seconds": 10,
        "sanitizer": "address",
    }


@pytest.fixture
def gitleaks_config() -> dict[str, Any]:
    """Return default Gitleaks configuration."""
    return {
        "config_path": None,
        "scan_uncommitted": True,
    }


@pytest.fixture
def file_scanner_config() -> dict[str, Any]:
    """Return default file scanner configuration."""
    return {
        "scan_patterns": ["*.py", "*.rs", "*.js"],
        "exclude_patterns": ["*.test.*", "*.spec.*"],
        "max_file_size": 1048576,  # 1MB
    }


# ============================================================================
# Module Instance Fixtures
# ============================================================================


@pytest.fixture
def atheris_fuzzer() -> AtherisFuzzer:
    """Create an AtherisFuzzer instance."""
    return AtherisFuzzer()


@pytest.fixture
def cargo_fuzzer() -> CargoFuzzer:
    """Create a CargoFuzzer instance."""
    return CargoFuzzer()


@pytest.fixture
def file_scanner() -> FileScanner:
    """Create a FileScanner instance."""
    return FileScanner()


@pytest.fixture
def security_analyzer() -> SecurityAnalyzer:
    """Create SecurityAnalyzer instance."""
    return SecurityAnalyzer()


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_stats_callback() -> Callable[[], CoroutineType]:
    """Mock stats callback for fuzzing."""
    stats_received = []

    async def callback(stats: dict[str, Any]) -> None:
        stats_received.append(stats)

    callback.stats_received = stats_received
    return callback


class MockActivityInfo:
    """Mock activity info."""

    def __init__(self) -> None:
        """Initialize an instance of the class."""
        self.workflow_id = "test-workflow-123"
        self.activity_id = "test-activity-1"
        self.attempt = 1


class MockContext:
    """Mock context."""

    def __init__(self) -> None:
        """Initialize an instance of the class."""
        self.info = MockActivityInfo()


@pytest.fixture
def mock_temporal_context() -> MockContext:
    """Mock Temporal activity context."""
    return MockContext()
