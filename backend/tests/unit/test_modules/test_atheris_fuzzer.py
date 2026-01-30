"""
Unit tests for AtherisFuzzer module
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
class TestAtherisFuzzerMetadata:
    """Test AtherisFuzzer metadata"""

    async def test_metadata_structure(self, atheris_fuzzer):
        """Test that module metadata is properly defined"""
        metadata = atheris_fuzzer.get_metadata()

        assert metadata.name == "atheris_fuzzer"
        assert metadata.category == "fuzzer"
        assert "fuzzing" in metadata.tags
        assert "python" in metadata.tags


@pytest.mark.asyncio
class TestAtherisFuzzerConfigValidation:
    """Test configuration validation"""

    async def test_valid_config(self, atheris_fuzzer, atheris_config):
        """Test validation of valid configuration"""
        assert atheris_fuzzer.validate_config(atheris_config) is True

    async def test_invalid_max_iterations(self, atheris_fuzzer):
        """Test validation fails with invalid max_iterations"""
        config = {
            "target_file": "fuzz_target.py",
            "max_iterations": -1,
            "timeout_seconds": 10
        }
        with pytest.raises(ValueError, match="max_iterations"):
            atheris_fuzzer.validate_config(config)

    async def test_invalid_timeout(self, atheris_fuzzer):
        """Test validation fails with invalid timeout"""
        config = {
            "target_file": "fuzz_target.py",
            "max_iterations": 1000,
            "timeout_seconds": 0
        }
        with pytest.raises(ValueError, match="timeout_seconds"):
            atheris_fuzzer.validate_config(config)


@pytest.mark.asyncio
class TestAtherisFuzzerDiscovery:
    """Test fuzz target discovery"""

    async def test_auto_discover(self, atheris_fuzzer, python_test_workspace):
        """Test auto-discovery of Python fuzz targets"""
        # Create a fuzz target file
        (python_test_workspace / "fuzz_target.py").write_text("""
import atheris
import sys

def TestOneInput(data):
    pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
""")

        # Pass None for auto-discovery
        target = atheris_fuzzer._discover_target(python_test_workspace, None)

        assert target is not None
        assert "fuzz_target.py" in str(target)


@pytest.mark.asyncio
class TestAtherisFuzzerExecution:
    """Test fuzzer execution logic"""

    async def test_execution_creates_result(self, atheris_fuzzer, python_test_workspace, atheris_config):
        """Test that execution returns a ModuleResult"""
        # Create a simple fuzz target
        (python_test_workspace / "fuzz_target.py").write_text("""
import atheris
import sys

def TestOneInput(data):
    if len(data) > 0:
        pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
""")

        # Use a very short timeout for testing
        test_config = {
            "target_file": "fuzz_target.py",
            "max_iterations": 10,
            "timeout_seconds": 1
        }

        # Mock the fuzzing subprocess to avoid actual execution
        with patch.object(atheris_fuzzer, '_run_fuzzing', new_callable=AsyncMock, return_value=([], {"total_executions": 10})):
            result = await atheris_fuzzer.execute(test_config, python_test_workspace)

            assert result.module == "atheris_fuzzer"
            assert result.status in ["success", "partial", "failed"]
            assert isinstance(result.execution_time, float)


@pytest.mark.asyncio
class TestAtherisFuzzerStatsCallback:
    """Test stats callback functionality"""

    async def test_stats_callback_invoked(self, atheris_fuzzer, python_test_workspace, atheris_config, mock_stats_callback):
        """Test that stats callback is invoked during fuzzing"""
        (python_test_workspace / "fuzz_target.py").write_text("""
import atheris
import sys

def TestOneInput(data):
    pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
""")

        # Mock fuzzing to simulate stats
        async def mock_run_fuzzing(test_one_input, target_path, workspace, max_iterations, timeout_seconds, stats_callback):
            if stats_callback:
                await stats_callback({
                    "total_execs": 100,
                    "execs_per_sec": 10.0,
                    "crashes": 0,
                    "coverage": 5,
                    "corpus_size": 2,
                    "elapsed_time": 10
                })
            return

        with patch.object(atheris_fuzzer, '_run_fuzzing', side_effect=mock_run_fuzzing):
            with patch.object(atheris_fuzzer, '_load_target_module', return_value=lambda x: None):
                # Put stats_callback in config dict, not as kwarg
                atheris_config["target_file"] = "fuzz_target.py"
                atheris_config["stats_callback"] = mock_stats_callback
                await atheris_fuzzer.execute(atheris_config, python_test_workspace)

                # Verify callback was invoked
                assert len(mock_stats_callback.stats_received) > 0


@pytest.mark.asyncio
class TestAtherisFuzzerFindingGeneration:
    """Test finding generation from crashes"""

    async def test_create_crash_finding(self, atheris_fuzzer):
        """Test crash finding creation"""
        finding = atheris_fuzzer.create_finding(
            title="Crash: Exception in TestOneInput",
            description="IndexError: list index out of range",
            severity="high",
            category="crash",
            file_path="fuzz_target.py",
            metadata={
                "crash_type": "IndexError",
                "stack_trace": "Traceback..."
            }
        )

        assert finding.title == "Crash: Exception in TestOneInput"
        assert finding.severity == "high"
        assert finding.category == "crash"
        assert "IndexError" in finding.metadata["crash_type"]
