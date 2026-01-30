"""
Unit tests for CargoFuzzer module
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
class TestCargoFuzzerMetadata:
    """Test CargoFuzzer metadata"""

    async def test_metadata_structure(self, cargo_fuzzer):
        """Test that module metadata is properly defined"""
        metadata = cargo_fuzzer.get_metadata()

        assert metadata.name == "cargo_fuzz"
        assert metadata.version == "0.11.2"
        assert metadata.category == "fuzzer"
        assert "fuzzing" in metadata.tags
        assert "rust" in metadata.tags


@pytest.mark.asyncio
class TestCargoFuzzerConfigValidation:
    """Test configuration validation"""

    async def test_valid_config(self, cargo_fuzzer, cargo_fuzz_config):
        """Test validation of valid configuration"""
        assert cargo_fuzzer.validate_config(cargo_fuzz_config) is True

    async def test_invalid_max_iterations(self, cargo_fuzzer):
        """Test validation fails with invalid max_iterations"""
        config = {
            "max_iterations": -1,
            "timeout_seconds": 10,
            "sanitizer": "address"
        }
        with pytest.raises(ValueError, match="max_iterations"):
            cargo_fuzzer.validate_config(config)

    async def test_invalid_timeout(self, cargo_fuzzer):
        """Test validation fails with invalid timeout"""
        config = {
            "max_iterations": 1000,
            "timeout_seconds": 0,
            "sanitizer": "address"
        }
        with pytest.raises(ValueError, match="timeout_seconds"):
            cargo_fuzzer.validate_config(config)

    async def test_invalid_sanitizer(self, cargo_fuzzer):
        """Test validation fails with invalid sanitizer"""
        config = {
            "max_iterations": 1000,
            "timeout_seconds": 10,
            "sanitizer": "invalid_sanitizer"
        }
        with pytest.raises(ValueError, match="sanitizer"):
            cargo_fuzzer.validate_config(config)


@pytest.mark.asyncio
class TestCargoFuzzerWorkspaceValidation:
    """Test workspace validation"""

    async def test_valid_workspace(self, cargo_fuzzer, rust_test_workspace):
        """Test validation of valid workspace"""
        assert cargo_fuzzer.validate_workspace(rust_test_workspace) is True

    async def test_nonexistent_workspace(self, cargo_fuzzer, tmp_path):
        """Test validation fails with nonexistent workspace"""
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            cargo_fuzzer.validate_workspace(nonexistent)

    async def test_workspace_is_file(self, cargo_fuzzer, tmp_path):
        """Test validation fails when workspace is a file"""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        with pytest.raises(ValueError, match="not a directory"):
            cargo_fuzzer.validate_workspace(file_path)


@pytest.mark.asyncio
class TestCargoFuzzerDiscovery:
    """Test fuzz target discovery"""

    async def test_discover_targets(self, cargo_fuzzer, rust_test_workspace):
        """Test discovery of fuzz targets"""
        targets = await cargo_fuzzer._discover_fuzz_targets(rust_test_workspace)

        assert len(targets) == 1
        assert "fuzz_target_1" in targets

    async def test_no_fuzz_directory(self, cargo_fuzzer, temp_workspace):
        """Test discovery with no fuzz directory"""
        targets = await cargo_fuzzer._discover_fuzz_targets(temp_workspace)

        assert targets == []


@pytest.mark.asyncio
class TestCargoFuzzerExecution:
    """Test fuzzer execution logic"""

    async def test_execution_creates_result(self, cargo_fuzzer, rust_test_workspace, cargo_fuzz_config):
        """Test that execution returns a ModuleResult"""
        # Mock the build and run methods to avoid actual fuzzing
        with patch.object(cargo_fuzzer, '_build_fuzz_target', new_callable=AsyncMock, return_value=True):
            with patch.object(cargo_fuzzer, '_run_fuzzing', new_callable=AsyncMock, return_value=([], {"total_executions": 0, "crashes_found": 0})):
                with patch.object(cargo_fuzzer, '_parse_crash_artifacts', new_callable=AsyncMock, return_value=[]):
                    result = await cargo_fuzzer.execute(cargo_fuzz_config, rust_test_workspace)

                    assert result.module == "cargo_fuzz"
                    assert result.status == "success"
                    assert isinstance(result.execution_time, float)
                    assert result.execution_time >= 0

    async def test_execution_with_no_targets(self, cargo_fuzzer, temp_workspace, cargo_fuzz_config):
        """Test execution fails gracefully with no fuzz targets"""
        result = await cargo_fuzzer.execute(cargo_fuzz_config, temp_workspace)

        assert result.status == "failed"
        assert "No fuzz targets found" in result.error


@pytest.mark.asyncio
class TestCargoFuzzerStatsCallback:
    """Test stats callback functionality"""

    async def test_stats_callback_invoked(self, cargo_fuzzer, rust_test_workspace, cargo_fuzz_config, mock_stats_callback):
        """Test that stats callback is invoked during fuzzing"""
        # Mock build/run to simulate stats generation
        async def mock_run_fuzzing(workspace, target, config, callback):
            # Simulate stats callback
            if callback:
                await callback({
                    "total_execs": 1000,
                    "execs_per_sec": 100.0,
                    "crashes": 0,
                    "coverage": 10,
                    "corpus_size": 5,
                    "elapsed_time": 10
                })
            return [], {"total_executions": 1000}

        with patch.object(cargo_fuzzer, '_build_fuzz_target', new_callable=AsyncMock, return_value=True):
            with patch.object(cargo_fuzzer, '_run_fuzzing', side_effect=mock_run_fuzzing):
                with patch.object(cargo_fuzzer, '_parse_crash_artifacts', new_callable=AsyncMock, return_value=[]):
                    await cargo_fuzzer.execute(cargo_fuzz_config, rust_test_workspace, stats_callback=mock_stats_callback)

                    # Verify callback was invoked
                    assert len(mock_stats_callback.stats_received) > 0
                    assert mock_stats_callback.stats_received[0]["total_execs"] == 1000


@pytest.mark.asyncio
class TestCargoFuzzerFindingGeneration:
    """Test finding generation from crashes"""

    async def test_create_finding_from_crash(self, cargo_fuzzer):
        """Test finding creation"""
        finding = cargo_fuzzer.create_finding(
            title="Crash: Segmentation Fault",
            description="Test crash",
            severity="critical",
            category="crash",
            file_path="fuzz/fuzz_targets/fuzz_target_1.rs",
            metadata={"crash_type": "SIGSEGV"}
        )

        assert finding.title == "Crash: Segmentation Fault"
        assert finding.severity == "critical"
        assert finding.category == "crash"
        assert finding.file_path == "fuzz/fuzz_targets/fuzz_target_1.rs"
        assert finding.metadata["crash_type"] == "SIGSEGV"
