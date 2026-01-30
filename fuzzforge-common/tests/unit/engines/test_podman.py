"""Tests for the PodmanCLI engine (OSS container engine)."""

import os
import shutil
import uuid
from pathlib import Path
from unittest import mock

import pytest

from fuzzforge_common.sandboxes.engines.podman.cli import PodmanCLI, _is_running_under_snap


@pytest.fixture
def podman_cli_engine() -> PodmanCLI:
    """Create a PodmanCLI engine with temporary storage.
    
    Uses short paths in /tmp to avoid podman's 50-char runroot limit.
    Simulates Snap environment to test custom storage paths.
    """
    short_id = str(uuid.uuid4())[:8]
    graphroot = Path(f"/tmp/ff-{short_id}/storage")
    runroot = Path(f"/tmp/ff-{short_id}/run")
    
    # Simulate Snap environment for testing
    with mock.patch.dict(os.environ, {"SNAP": "/snap/code/123"}):
        engine = PodmanCLI(graphroot=graphroot, runroot=runroot)
    
    yield engine
    
    # Cleanup
    parent = graphroot.parent
    if parent.exists():
        shutil.rmtree(parent, ignore_errors=True)


def test_snap_detection_when_snap_set() -> None:
    """Test that SNAP environment is detected."""
    with mock.patch.dict(os.environ, {"SNAP": "/snap/code/123"}):
        assert _is_running_under_snap() is True


def test_snap_detection_when_snap_not_set() -> None:
    """Test that non-Snap environment is detected."""
    env = os.environ.copy()
    env.pop("SNAP", None)
    with mock.patch.dict(os.environ, env, clear=True):
        assert _is_running_under_snap() is False


def test_podman_cli_creates_storage_directories_under_snap() -> None:
    """Test that PodmanCLI creates storage directories when under Snap."""
    short_id = str(uuid.uuid4())[:8]
    graphroot = Path(f"/tmp/ff-{short_id}/storage")
    runroot = Path(f"/tmp/ff-{short_id}/run")
    
    assert not graphroot.exists()
    assert not runroot.exists()
    
    with mock.patch.dict(os.environ, {"SNAP": "/snap/code/123"}):
        engine = PodmanCLI(graphroot=graphroot, runroot=runroot)
    
    assert graphroot.exists()
    assert runroot.exists()
    
    # Cleanup
    shutil.rmtree(graphroot.parent, ignore_errors=True)


def test_podman_cli_base_cmd_under_snap() -> None:
    """Test that base command includes --root/--runroot under Snap."""
    short_id = str(uuid.uuid4())[:8]
    graphroot = Path(f"/tmp/ff-{short_id}/storage")
    runroot = Path(f"/tmp/ff-{short_id}/run")
    
    with mock.patch.dict(os.environ, {"SNAP": "/snap/code/123"}):
        engine = PodmanCLI(graphroot=graphroot, runroot=runroot)
        base_cmd = engine._base_cmd()
    
    assert "podman" in base_cmd
    assert "--root" in base_cmd
    assert "--runroot" in base_cmd
    
    # Cleanup
    shutil.rmtree(graphroot.parent, ignore_errors=True)


def test_podman_cli_base_cmd_without_snap() -> None:
    """Test that base command is plain 'podman' when not under Snap."""
    short_id = str(uuid.uuid4())[:8]
    graphroot = Path(f"/tmp/ff-{short_id}/storage")
    runroot = Path(f"/tmp/ff-{short_id}/run")
    
    env = os.environ.copy()
    env.pop("SNAP", None)
    with mock.patch.dict(os.environ, env, clear=True):
        engine = PodmanCLI(graphroot=graphroot, runroot=runroot)
        base_cmd = engine._base_cmd()
    
    assert base_cmd == ["podman"]
    assert "--root" not in base_cmd
    
    # Directories should NOT be created when not under Snap
    assert not graphroot.exists()


def test_podman_cli_default_mode() -> None:
    """Test PodmanCLI without custom storage paths."""
    engine = PodmanCLI()  # No paths provided
    base_cmd = engine._base_cmd()
    
    assert base_cmd == ["podman"]
    assert "--root" not in base_cmd


def test_podman_cli_list_images_returns_list(podman_cli_engine: PodmanCLI) -> None:
    """Test that list_images returns a list (even if empty)."""
    images = podman_cli_engine.list_images()
    
    assert isinstance(images, list)


@pytest.mark.skip(reason="Requires pulling images, slow integration test")
def test_podman_cli_can_pull_and_list_image(podman_cli_engine: PodmanCLI) -> None:
    """Test pulling an image and listing it."""
    # Pull a small image
    podman_cli_engine._run(["pull", "docker.io/library/alpine:latest"])
    
    images = podman_cli_engine.list_images()
    assert any("alpine" in img.identifier for img in images)
