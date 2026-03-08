"""Common test fixtures for FuzzForge packages.

Provides reusable fixtures for generating random identifiers and other
common test utilities shared across multiple FuzzForge packages.

"""

import random
import string
from os import environ
from typing import TYPE_CHECKING
from uuid import uuid4, uuid7

import pytest
from fuzzforge_common.sandboxes.engines.podman.configuration import PodmanConfiguration
from podman import PodmanClient
from pydantic import UUID7

# Type aliases for identifiers
type FuzzForgeProjectIdentifier = UUID7
type FuzzForgeExecutionIdentifier = UUID7

# Constants for validation
FUZZFORGE_PROJECT_NAME_LENGTH_MIN: int = 3
FUZZFORGE_PROJECT_NAME_LENGTH_MAX: int = 64
FUZZFORGE_PROJECT_DESCRIPTION_LENGTH_MAX: int = 256

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path


def generate_random_string(
    min_length: int,
    max_length: int,
) -> str:
    """TODO."""
    return "".join(random.choices(population=string.printable, k=random.randint(min_length, max_length)))  # noqa: S311


# ===== Project Fixtures =====


@pytest.fixture
def random_project_name() -> Callable[[], str]:
    """Generate random project names."""

    def inner() -> str:
        return generate_random_string(
            min_length=FUZZFORGE_PROJECT_NAME_LENGTH_MIN,
            max_length=FUZZFORGE_PROJECT_NAME_LENGTH_MAX,
        )

    return inner


@pytest.fixture
def random_project_description() -> Callable[[], str]:
    """Generate random project descriptions."""

    def inner() -> str:
        return generate_random_string(
            min_length=1,
            max_length=FUZZFORGE_PROJECT_DESCRIPTION_LENGTH_MAX,
        )

    return inner


@pytest.fixture
def random_project_identifier() -> Callable[[], FuzzForgeProjectIdentifier]:
    """Generate random project identifiers.

    Returns a callable that generates fresh UUID7 identifiers for each call.
    This pattern allows generating multiple unique identifiers within a single test.

    :return: Callable that generates project identifiers.

    """

    def inner() -> FuzzForgeProjectIdentifier:
        return uuid7()

    return inner


@pytest.fixture
def random_execution_identifier() -> Callable[[], FuzzForgeExecutionIdentifier]:
    """Generate random execution identifiers.

    Returns a callable that generates fresh UUID7 identifiers for each call.
    This pattern allows generating multiple unique identifiers within a single test.

    :return: Callable that generates execution identifiers.

    """

    def inner() -> FuzzForgeExecutionIdentifier:
        return uuid7()

    return inner


@pytest.fixture
def podman_socket() -> str:
    """TODO."""
    socket: str = environ.get("DOCKER_HOST", "")
    return socket


@pytest.fixture
def podman_client(podman_socket: str) -> Generator[PodmanClient]:
    """TODO."""
    with PodmanClient(base_url=podman_socket) as client:
        yield client


@pytest.fixture
def podman_engine_configuration(podman_socket: str) -> PodmanConfiguration:
    """TODO."""
    return PodmanConfiguration(socket=podman_socket)


DOCKERFILE: str = 'FROM docker.io/debian:trixie\nCMD ["/bin/sh"]'


@pytest.fixture
def path_to_oci(podman_client: PodmanClient, tmp_path: Path) -> Generator[Path]:
    """TODO."""
    dockerfile: Path = tmp_path / "Dockerfile"
    dockerfile.write_text(DOCKERFILE)
    identifier = str(uuid4())
    image, _ = podman_client.images.build(
        path=tmp_path,
        dockerfile=dockerfile.name,
        tag=identifier,
    )
    path: Path = tmp_path / "image.oci"
    with path.open(mode="wb") as file:
        for chunk in image.save():
            file.write(chunk)
    podman_client.images.get(name=identifier).remove()
    yield path
    path.unlink(missing_ok=True)
