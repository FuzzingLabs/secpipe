"""
Benchmark fixtures and configuration
"""

import sys
from pathlib import Path
import pytest

# Add parent directories to path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
TOOLBOX = BACKEND_ROOT / "toolbox"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(TOOLBOX) not in sys.path:
    sys.path.insert(0, str(TOOLBOX))


# ============================================================================
# Benchmark Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def benchmark_fixtures_dir():
    """Path to benchmark fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def small_project_fixture(benchmark_fixtures_dir):
    """Small project fixture (~1K LOC)"""
    return benchmark_fixtures_dir / "small"


@pytest.fixture(scope="session")
def medium_project_fixture(benchmark_fixtures_dir):
    """Medium project fixture (~10K LOC)"""
    return benchmark_fixtures_dir / "medium"


@pytest.fixture(scope="session")
def large_project_fixture(benchmark_fixtures_dir):
    """Large project fixture (~100K LOC)"""
    return benchmark_fixtures_dir / "large"


# ============================================================================
# pytest-benchmark Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest-benchmark"""
    config.addinivalue_line(
        "markers", "benchmark: mark test as a benchmark"
    )


def pytest_benchmark_group_stats(config, benchmarks, group_by):
    """Group benchmark results by category"""
    return group_by
