"""
Unit tests for platform detection and Dockerfile selection in WorkerManager.

These tests verify that the WorkerManager correctly detects the platform
and selects the appropriate Dockerfile for workers with platform-specific
configurations (e.g., Android worker with separate AMD64 and ARM64 Dockerfiles).
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import yaml

from fuzzforge_cli.worker_manager import WorkerManager


@pytest.fixture
def worker_manager(tmp_path):
    """Create a WorkerManager instance for testing."""
    # Create a dummy docker-compose.yml for testing
    dummy_compose = tmp_path / "docker-compose.yml"
    dummy_compose.write_text("version: '3.8'\nservices: {}")
    return WorkerManager(compose_file=dummy_compose)


@pytest.fixture
def mock_android_metadata():
    """Mock metadata.yaml content for Android worker."""
    return """
name: android
version: "1.0.0"
description: "Android application security testing worker"
default_platform: linux/amd64

platforms:
  linux/amd64:
    dockerfile: Dockerfile.amd64
    description: "Full Android toolchain with MobSF support"
    supported_tools:
      - jadx
      - opengrep
      - mobsf
      - frida
      - androguard

  linux/arm64:
    dockerfile: Dockerfile.arm64
    description: "Android toolchain without MobSF (ARM64/Apple Silicon compatible)"
    supported_tools:
      - jadx
      - opengrep
      - frida
      - androguard
    disabled_tools:
      mobsf: "Incompatible with Rosetta 2 emulation"
"""


class TestPlatformDetection:
    """Test platform detection logic."""

    def test_detect_platform_linux_x86_64(self, worker_manager):
        """Test platform detection on Linux x86_64."""
        with patch('platform.machine', return_value='x86_64'), \
             patch('platform.system', return_value='Linux'):
            platform = worker_manager._detect_platform()
            assert platform == 'linux/amd64'

    def test_detect_platform_linux_aarch64(self, worker_manager):
        """Test platform detection on Linux aarch64."""
        with patch('platform.machine', return_value='aarch64'), \
             patch('platform.system', return_value='Linux'):
            platform = worker_manager._detect_platform()
            assert platform == 'linux/arm64'

    def test_detect_platform_darwin_arm64(self, worker_manager):
        """Test platform detection on macOS Apple Silicon."""
        with patch('platform.machine', return_value='arm64'), \
             patch('platform.system', return_value='Darwin'):
            platform = worker_manager._detect_platform()
            assert platform == 'linux/arm64'

    def test_detect_platform_darwin_x86_64(self, worker_manager):
        """Test platform detection on macOS Intel."""
        with patch('platform.machine', return_value='x86_64'), \
             patch('platform.system', return_value='Darwin'):
            platform = worker_manager._detect_platform()
            assert platform == 'linux/amd64'


class TestDockerfileSelection:
    """Test Dockerfile selection logic."""

    def test_select_dockerfile_with_metadata_amd64(self, worker_manager, mock_android_metadata):
        """Test Dockerfile selection for AMD64 platform with metadata."""
        with patch('platform.machine', return_value='x86_64'), \
             patch('platform.system', return_value='Linux'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_android_metadata)):

            dockerfile = worker_manager._select_dockerfile('android')
            assert 'Dockerfile.amd64' in str(dockerfile)

    def test_select_dockerfile_with_metadata_arm64(self, worker_manager, mock_android_metadata):
        """Test Dockerfile selection for ARM64 platform with metadata."""
        with patch('platform.machine', return_value='arm64'), \
             patch('platform.system', return_value='Darwin'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_android_metadata)):

            dockerfile = worker_manager._select_dockerfile('android')
            assert 'Dockerfile.arm64' in str(dockerfile)

    def test_select_dockerfile_without_metadata(self, worker_manager):
        """Test Dockerfile selection for worker without metadata (uses default Dockerfile)."""
        with patch('pathlib.Path.exists', return_value=False):
            dockerfile = worker_manager._select_dockerfile('python')
            assert str(dockerfile).endswith('Dockerfile')
            assert 'Dockerfile.amd64' not in str(dockerfile)
            assert 'Dockerfile.arm64' not in str(dockerfile)

    def test_select_dockerfile_fallback_to_default(self, worker_manager):
        """Test Dockerfile selection falls back to default platform when current platform not found."""
        # Metadata with only amd64 support
        limited_metadata = """
name: test-worker
default_platform: linux/amd64
platforms:
  linux/amd64:
    dockerfile: Dockerfile.amd64
"""
        with patch('platform.machine', return_value='arm64'), \
             patch('platform.system', return_value='Darwin'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=limited_metadata)):

            # Should fall back to default_platform (amd64) since arm64 is not defined
            dockerfile = worker_manager._select_dockerfile('test-worker')
            assert 'Dockerfile.amd64' in str(dockerfile)


class TestMetadataParsing:
    """Test metadata.yaml parsing and handling."""

    def test_parse_valid_metadata(self, worker_manager, mock_android_metadata):
        """Test parsing valid metadata.yaml."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_android_metadata)):

            metadata_path = Path("workers/android/metadata.yaml")
            with open(metadata_path, 'r') as f:
                metadata = yaml.safe_load(f)

            assert metadata['name'] == 'android'
            assert metadata['default_platform'] == 'linux/amd64'
            assert 'linux/amd64' in metadata['platforms']
            assert 'linux/arm64' in metadata['platforms']
            assert metadata['platforms']['linux/amd64']['dockerfile'] == 'Dockerfile.amd64'
            assert metadata['platforms']['linux/arm64']['dockerfile'] == 'Dockerfile.arm64'

    def test_handle_missing_metadata(self, worker_manager):
        """Test handling when metadata.yaml doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            # Should use default Dockerfile when metadata doesn't exist
            dockerfile = worker_manager._select_dockerfile('nonexistent-worker')
            assert str(dockerfile).endswith('Dockerfile')

    def test_handle_malformed_metadata(self, worker_manager):
        """Test handling malformed metadata.yaml."""
        malformed_yaml = "{ invalid: yaml: content:"

        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=malformed_yaml)):

            # Should fall back to default Dockerfile on YAML parse error
            dockerfile = worker_manager._select_dockerfile('broken-worker')
            assert str(dockerfile).endswith('Dockerfile')


class TestWorkerStartWithPlatform:
    """Test worker startup with platform-specific configuration."""

    def test_start_android_worker_amd64(self, worker_manager, mock_android_metadata):
        """Test starting Android worker on AMD64 platform."""
        with patch('platform.machine', return_value='x86_64'), \
             patch('platform.system', return_value='Linux'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_android_metadata)), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = Mock(returncode=0)

            # This would call _select_dockerfile internally
            dockerfile = worker_manager._select_dockerfile('android')
            assert 'Dockerfile.amd64' in str(dockerfile)

            # Verify it would use MobSF-enabled image
            with open(Path("workers/android/metadata.yaml"), 'r') as f:
                metadata = yaml.safe_load(f)
            tools = metadata['platforms']['linux/amd64']['supported_tools']
            assert 'mobsf' in tools

    def test_start_android_worker_arm64(self, worker_manager, mock_android_metadata):
        """Test starting Android worker on ARM64 platform."""
        with patch('platform.machine', return_value='arm64'), \
             patch('platform.system', return_value='Darwin'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_android_metadata)), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = Mock(returncode=0)

            # This would call _select_dockerfile internally
            dockerfile = worker_manager._select_dockerfile('android')
            assert 'Dockerfile.arm64' in str(dockerfile)

            # Verify MobSF is disabled on ARM64
            with open(Path("workers/android/metadata.yaml"), 'r') as f:
                metadata = yaml.safe_load(f)
            tools = metadata['platforms']['linux/arm64']['supported_tools']
            assert 'mobsf' not in tools
            assert 'mobsf' in metadata['platforms']['linux/arm64']['disabled_tools']


@pytest.mark.integration
class TestPlatformDetectionIntegration:
    """Integration tests that verify actual platform detection."""

    def test_current_platform_detection(self, worker_manager):
        """Test that platform detection works on current platform."""
        platform = worker_manager._detect_platform()

        # Should be one of the supported platforms
        assert platform in ['linux/amd64', 'linux/arm64']

        # Should match the actual system
        import platform as sys_platform
        machine = sys_platform.machine()

        if machine in ['x86_64', 'AMD64']:
            assert platform == 'linux/amd64'
        elif machine in ['aarch64', 'arm64']:
            assert platform == 'linux/arm64'

    def test_android_metadata_exists(self):
        """Test that Android worker metadata file exists."""
        metadata_path = Path(__file__).parent.parent.parent / "workers" / "android" / "metadata.yaml"
        assert metadata_path.exists(), "Android worker metadata.yaml should exist"

        # Verify it's valid YAML
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f)

        assert 'platforms' in metadata
        assert 'linux/amd64' in metadata['platforms']
        assert 'linux/arm64' in metadata['platforms']
