"""Tests for the DockerCLI engine."""

from unittest import mock

import pytest

from fuzzforge_common.sandboxes.engines.docker.cli import DockerCLI


def test_docker_cli_base_cmd() -> None:
    """Test that base command is just 'docker'."""
    engine = DockerCLI()
    base_cmd = engine._base_cmd()
    
    assert base_cmd == ["docker"]


def test_docker_cli_list_images_returns_list() -> None:
    """Test that list_images returns a list (mocked)."""
    engine = DockerCLI()
    
    # Mock the _run method to return empty JSON
    with mock.patch.object(engine, "_run") as mock_run:
        mock_run.return_value = mock.Mock(stdout="", returncode=0)
        images = engine.list_images()
    
    assert isinstance(images, list)
    assert len(images) == 0


def test_docker_cli_list_images_parses_output() -> None:
    """Test that list_images correctly parses Docker JSON output."""
    engine = DockerCLI()
    
    # Docker outputs one JSON object per line
    docker_output = '{"Repository":"alpine","Tag":"latest","ID":"abc123","Size":"5MB"}\n{"Repository":"ubuntu","Tag":"22.04","ID":"def456","Size":"77MB"}'
    
    with mock.patch.object(engine, "_run") as mock_run:
        mock_run.return_value = mock.Mock(stdout=docker_output, returncode=0)
        images = engine.list_images()
    
    assert len(images) == 2
    assert images[0].repository == "alpine"
    assert images[0].tag == "latest"
    assert images[1].repository == "ubuntu"
    assert images[1].tag == "22.04"


def test_docker_cli_image_exists_mocked() -> None:
    """Test image_exists with mocked response."""
    engine = DockerCLI()
    
    with mock.patch.object(engine, "_run") as mock_run:
        # Image exists
        mock_run.return_value = mock.Mock(returncode=0)
        assert engine.image_exists("alpine:latest") is True
        
        # Image doesn't exist
        mock_run.return_value = mock.Mock(returncode=1)
        assert engine.image_exists("nonexistent:image") is False


def test_docker_cli_create_container_with_volumes() -> None:
    """Test create_container generates correct command with volumes."""
    engine = DockerCLI()
    
    with mock.patch.object(engine, "_run") as mock_run:
        mock_run.return_value = mock.Mock(stdout="container123\n", returncode=0)
        
        container_id = engine.create_container(
            "alpine:latest",
            volumes={"/host/path": "/container/path"}
        )
        
        # Check the command was called with volume flag
        call_args = mock_run.call_args[0][0]
        assert "create" in call_args
        assert "-v" in call_args
        assert "/host/path:/container/path:ro" in call_args
        assert "alpine:latest" in call_args
        assert container_id == "container123"
