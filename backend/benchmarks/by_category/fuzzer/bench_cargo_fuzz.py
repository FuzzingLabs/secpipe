"""
Benchmarks for CargoFuzzer module

Tests performance characteristics of Rust fuzzing:
- Execution throughput (execs/sec)
- Coverage rate
- Memory efficiency
- Time to first crash
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "toolbox"))

from modules.fuzzer.cargo_fuzzer import CargoFuzzer
from benchmarks.category_configs import ModuleCategory, get_threshold


@pytest.fixture
def cargo_fuzzer():
    """Create CargoFuzzer instance for benchmarking"""
    return CargoFuzzer()


@pytest.fixture
def benchmark_config():
    """Benchmark-optimized configuration"""
    return {
        "target_name": None,
        "max_iterations": 10000,  # Fixed iterations for consistent benchmarking
        "timeout_seconds": 30,
        "sanitizer": "address"
    }


@pytest.fixture
def mock_rust_workspace(tmp_path):
    """Create a minimal Rust workspace for benchmarking"""
    workspace = tmp_path / "rust_project"
    workspace.mkdir()

    # Cargo.toml
    (workspace / "Cargo.toml").write_text("""[package]
name = "bench_project"
version = "0.1.0"
edition = "2021"
""")

    # src/lib.rs
    src = workspace / "src"
    src.mkdir()
    (src / "lib.rs").write_text("""
pub fn benchmark_function(data: &[u8]) -> Vec<u8> {
    data.to_vec()
}
""")

    # fuzz structure
    fuzz = workspace / "fuzz"
    fuzz.mkdir()
    (fuzz / "Cargo.toml").write_text("""[package]
name = "bench_project-fuzz"
version = "0.0.0"
edition = "2021"

[dependencies]
libfuzzer-sys = "0.4"

[dependencies.bench_project]
path = ".."

[[bin]]
name = "fuzz_target_1"
path = "fuzz_targets/fuzz_target_1.rs"
""")

    targets = fuzz / "fuzz_targets"
    targets.mkdir()
    (targets / "fuzz_target_1.rs").write_text("""#![no_main]
use libfuzzer_sys::fuzz_target;
use bench_project::benchmark_function;

fuzz_target!(|data: &[u8]| {
    let _ = benchmark_function(data);
});
""")

    return workspace


class TestCargoFuzzerPerformance:
    """Benchmark CargoFuzzer performance metrics"""

    @pytest.mark.benchmark(group="fuzzer")
    def test_target_discovery_performance(self, benchmark, cargo_fuzzer, mock_rust_workspace):
        """Benchmark fuzz target discovery speed"""
        def discover():
            return asyncio.run(cargo_fuzzer._discover_fuzz_targets(mock_rust_workspace))

        result = benchmark(discover)
        assert len(result) > 0

    @pytest.mark.benchmark(group="fuzzer")
    def test_config_validation_performance(self, benchmark, cargo_fuzzer, benchmark_config):
        """Benchmark configuration validation speed"""
        result = benchmark(cargo_fuzzer.validate_config, benchmark_config)
        assert result is True

    @pytest.mark.benchmark(group="fuzzer")
    def test_module_initialization_performance(self, benchmark):
        """Benchmark module instantiation time"""
        def init_module():
            return CargoFuzzer()

        module = benchmark(init_module)
        assert module is not None


class TestCargoFuzzerThroughput:
    """Benchmark execution throughput"""

    @pytest.mark.benchmark(group="fuzzer")
    def test_execution_throughput(self, benchmark, cargo_fuzzer, mock_rust_workspace, benchmark_config):
        """Benchmark fuzzing execution throughput"""

        # Mock actual fuzzing to focus on orchestration overhead
        async def mock_run(workspace, target, config, callback):
            # Simulate 10K execs at 1000 execs/sec
            if callback:
                await callback({
                    "total_execs": 10000,
                    "execs_per_sec": 1000.0,
                    "crashes": 0,
                    "coverage": 50,
                    "corpus_size": 10,
                    "elapsed_time": 10
                })
            return [], {"total_executions": 10000, "execution_time": 10.0}

        with patch.object(cargo_fuzzer, '_build_fuzz_target', new_callable=AsyncMock, return_value=True):
            with patch.object(cargo_fuzzer, '_run_fuzzing', side_effect=mock_run):
                with patch.object(cargo_fuzzer, '_parse_crash_artifacts', new_callable=AsyncMock, return_value=[]):
                    def run_fuzzer():
                        # Run in new event loop
                        loop = asyncio.new_event_loop()
                        try:
                            return loop.run_until_complete(
                                cargo_fuzzer.execute(benchmark_config, mock_rust_workspace)
                            )
                        finally:
                            loop.close()

                    result = benchmark(run_fuzzer)
                    assert result.status == "success"

                    # Verify performance threshold
                    threshold = get_threshold(ModuleCategory.FUZZER, "max_execution_time_small")
                    assert result.execution_time < threshold, \
                        f"Execution time {result.execution_time}s exceeds threshold {threshold}s"


class TestCargoFuzzerMemory:
    """Benchmark memory efficiency"""

    @pytest.mark.benchmark(group="fuzzer")
    def test_memory_overhead(self, benchmark, cargo_fuzzer, mock_rust_workspace, benchmark_config):
        """Benchmark memory usage during execution"""
        import tracemalloc

        def measure_memory():
            tracemalloc.start()

            # Simulate operations
            cargo_fuzzer.validate_config(benchmark_config)
            asyncio.run(cargo_fuzzer._discover_fuzz_targets(mock_rust_workspace))

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            return peak / 1024 / 1024  # Convert to MB

        peak_mb = benchmark(measure_memory)

        # Check against threshold
        max_memory = get_threshold(ModuleCategory.FUZZER, "max_memory_mb")
        assert peak_mb < max_memory, \
            f"Peak memory {peak_mb:.2f}MB exceeds threshold {max_memory}MB"


class TestCargoFuzzerScalability:
    """Benchmark scalability characteristics"""

    @pytest.mark.benchmark(group="fuzzer")
    def test_multiple_target_discovery(self, benchmark, cargo_fuzzer, tmp_path):
        """Benchmark discovery with multiple targets"""
        workspace = tmp_path / "multi_target"
        workspace.mkdir()

        # Create workspace with 10 fuzz targets
        (workspace / "Cargo.toml").write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\nedition = \"2021\"")
        src = workspace / "src"
        src.mkdir()
        (src / "lib.rs").write_text("pub fn test() {}")

        fuzz = workspace / "fuzz"
        fuzz.mkdir()
        targets = fuzz / "fuzz_targets"
        targets.mkdir()

        for i in range(10):
            (targets / f"fuzz_target_{i}.rs").write_text("// Target")

        def discover():
            return asyncio.run(cargo_fuzzer._discover_fuzz_targets(workspace))

        result = benchmark(discover)
        assert len(result) == 10
