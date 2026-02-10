"""Common test fixtures for FuzzForge packages.

Provides reusable fixtures for generating random identifiers and other
common test utilities shared across multiple FuzzForge packages.

"""

import random
import string
from os import environ
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4, uuid7

import boto3
import pytest
from fuzzforge_common.sandboxes.engines.podman.configuration import PodmanConfiguration
from fuzzforge_common.storage.configuration import StorageConfiguration
from podman import PodmanClient
from testcontainers.minio import MinioContainer

# Constants for validation (moved from enterprise SDK)
FUZZFORGE_PROJECT_NAME_LENGTH_MIN: int = 3
FUZZFORGE_PROJECT_NAME_LENGTH_MAX: int = 64
FUZZFORGE_PROJECT_DESCRIPTION_LENGTH_MAX: int = 256

FUZZFORGE_MODULE_NAME_LENGTH_MIN: int = 3
FUZZFORGE_MODULE_NAME_LENGTH_MAX: int = 64
FUZZFORGE_MODULE_DESCRIPTION_LENGTH_MAX: int = 256

FUZZFORGE_WORKFLOW_NAME_LENGTH_MIN: int = 3
FUZZFORGE_WORKFLOW_NAME_LENGTH_MAX: int = 64
FUZZFORGE_WORKFLOW_DESCRIPTION_LENGTH_MAX: int = 256

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

    from fuzzforge_types import (
        FuzzForgeExecutionIdentifier,
        FuzzForgeModuleIdentifier,
        FuzzForgeProjectIdentifier,
        FuzzForgeWorkflowIdentifier,
    )


MINIO_DEFAULT_IMAGE: str = "minio/minio:RELEASE.2025-09-07T16-13-09Z"


def generate_random_string(
    min_length: int,
    max_length: int,
) -> str:
    """TODO."""
    return "".join(random.choices(population=string.printable, k=random.randint(min_length, max_length)))  # noqa: S311


# ===== Project Fixtures =====
# Note: random_project_identifier is provided by fuzzforge-tests
# Note: random_module_execution_identifier is provided by fuzzforge-tests


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
def random_module_name() -> Callable[[], str]:
    """Generate random module names."""

    def inner() -> str:
        return generate_random_string(
            min_length=FUZZFORGE_MODULE_NAME_LENGTH_MIN,
            max_length=FUZZFORGE_MODULE_NAME_LENGTH_MAX,
        )

    return inner


@pytest.fixture
def random_module_description() -> Callable[[], str]:
    """Generate random module descriptions."""

    def inner() -> str:
        return generate_random_string(
            min_length=1,
            max_length=FUZZFORGE_MODULE_DESCRIPTION_LENGTH_MAX,
        )

    return inner


@pytest.fixture
def random_workflow_identifier() -> Callable[[], FuzzForgeWorkflowIdentifier]:
    """Generate random workflow identifiers."""

    def inner() -> FuzzForgeWorkflowIdentifier:
        return uuid7()

    return inner


@pytest.fixture
def random_workflow_name() -> Callable[[], str]:
    """Generate random workflow names."""

    def inner() -> str:
        return generate_random_string(
            min_length=FUZZFORGE_WORKFLOW_NAME_LENGTH_MIN,
            max_length=FUZZFORGE_WORKFLOW_NAME_LENGTH_MAX,
        )

    return inner


@pytest.fixture
def random_workflow_description() -> Callable[[], str]:
    """Generate random workflow descriptions."""

    def inner() -> str:
        return generate_random_string(
            min_length=1,
            max_length=FUZZFORGE_WORKFLOW_DESCRIPTION_LENGTH_MAX,
        )

    return inner


@pytest.fixture
def random_workflow_execution_identifier() -> Callable[[], FuzzForgeExecutionIdentifier]:
    """Generate random workflow execution identifiers."""

    def inner() -> FuzzForgeExecutionIdentifier:
        return uuid7()

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
def random_module_identifier() -> Callable[[], FuzzForgeModuleIdentifier]:
    """Generate random module identifiers."""

    def inner() -> FuzzForgeModuleIdentifier:
        return uuid7()

    return inner


@pytest.fixture
def random_module_execution_identifier() -> Callable[[], FuzzForgeExecutionIdentifier]:
    """Generate random workflow execution identifiers.

    Returns a callable that generates fresh UUID7 identifiers for each call.
    This pattern allows generating multiple unique identifiers within a single test.

    :return: Callable that generates execution identifiers.

    """

    def inner() -> FuzzForgeExecutionIdentifier:
        return uuid7()

    return inner


@pytest.fixture(scope="session")
def minio_container() -> Generator[MinioContainer]:
    """Provide MinIO testcontainer for test session.

    Creates a MinIO container that persists for the entire test session.
    All tests share the same container but use different buckets/keys.

    :return: MinIO container instance.

    """
    with MinioContainer(image=MINIO_DEFAULT_IMAGE) as container:
        yield container


@pytest.fixture
def minio_container_configuration(minio_container: MinioContainer) -> dict[str, str]:
    """TODO."""
    return cast("dict[str, str]", minio_container.get_config())


@pytest.fixture
def storage_configuration(minio_container_configuration: dict[str, str]) -> StorageConfiguration:
    """Provide S3 storage backend connected to MinIO testcontainer.

    Creates the bucket in MinIO before returning the backend instance.

    :param minio_container: MinIO testcontainer fixture.
    :return: Configured S3StorageBackend instance with bucket already created.

    """
    return StorageConfiguration(
        endpoint=f"http://{minio_container_configuration['endpoint']}",
        access_key=minio_container_configuration["access_key"],
        secret_key=minio_container_configuration["secret_key"],
    )


@pytest.fixture
def boto3_client(minio_container_configuration: dict[str, str]) -> Any:
    """TODO."""
    return boto3.client(
        "s3",
        endpoint_url=f"http://{minio_container_configuration['endpoint']}",
        aws_access_key_id=minio_container_configuration["access_key"],
        aws_secret_access_key=minio_container_configuration["secret_key"],
    )


@pytest.fixture
def random_bucket(
    boto3_client: Any,
    random_project_identifier: Callable[[], FuzzForgeProjectIdentifier],
) -> str:
    """TODO."""
    project_identifier: FuzzForgeProjectIdentifier = random_project_identifier()
    boto3_client.create_bucket(Bucket=str(project_identifier))
    return str(project_identifier)


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
