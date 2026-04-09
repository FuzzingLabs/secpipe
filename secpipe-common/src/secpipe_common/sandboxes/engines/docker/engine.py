from __future__ import annotations

from typing import TYPE_CHECKING

from secpipe_common.sandboxes.engines.base.engine import AbstractSecPipeSandboxEngine, ImageInfo

if TYPE_CHECKING:
    from pathlib import Path, PurePath


class Docker(AbstractSecPipeSandboxEngine):
    """TODO."""

    #: TODO.
    __socket: str

    def __init__(self, socket: str) -> None:
        """Initialize an instance of the class.

        :param socket: TODO.

        """
        super().__init__()
        self.__socket = socket

    def list_images(self, filter_prefix: str | None = None) -> list[ImageInfo]:
        """List available container images.

        :param filter_prefix: Optional prefix to filter images (e.g., "localhost/").
        :returns: List of ImageInfo objects for available images.

        """
        # TODO: Implement Docker image listing
        message: str = "Docker engine list_images is not yet implemented"
        raise NotImplementedError(message)

    def register_archive(self, archive: Path, repository: str) -> None:
        """TODO.

        :param archive: TODO.

        """
        return super().register_archive(archive=archive, repository=repository)

    def spawn_sandbox(self, image: str) -> str:
        """Spawn a sandbox based on the given image.

        :param image: The image the sandbox should be based on.
        :returns: The sandbox identifier.

        """
        return super().spawn_sandbox(image)

    def push_archive_to_sandbox(self, identifier: str, source: Path, destination: PurePath) -> None:
        """TODO.

        :param identifier: TODO.
        :param source: TODO.
        :param destination: TODO.

        """
        super().push_archive_to_sandbox(identifier, source, destination)

    def start_sandbox(self, identifier: str) -> None:
        """TODO.

        :param identifier: The identifier of the sandbox to start.

        """
        super().start_sandbox(identifier)

    def execute_inside_sandbox(self, identifier: str, command: list[str]) -> None:
        """Execute a command inside the sandbox matching the given identifier and wait for completion.

        :param sandbox: The identifier of the sandbox.
        :param command: The command to run.

        """
        super().execute_inside_sandbox(identifier, command)

    def pull_archive_from_sandbox(self, identifier: str, source: PurePath) -> Path:
        """TODO.

        :param identifier: TODO.
        :param source: TODO.
        :returns: TODO.

        """
        return super().pull_archive_from_sandbox(identifier, source)

    def terminate_sandbox(self, identifier: str) -> None:
        """Terminate the sandbox matching the given identifier.

        :param identifier: The identifier of the sandbox to terminate.

        """
        super().terminate_sandbox(identifier)

    # -------------------------------------------------------------------------
    # Extended Container Operations (stubs - not yet implemented)
    # -------------------------------------------------------------------------

    def image_exists(self, image: str) -> bool:
        """Check if a container image exists locally."""
        message: str = "Docker engine image_exists is not yet implemented"
        raise NotImplementedError(message)

    def pull_image(self, image: str, timeout: int = 300) -> None:
        """Pull an image from a container registry."""
        message: str = "Docker engine pull_image is not yet implemented"
        raise NotImplementedError(message)

    def tag_image(self, source: str, target: str) -> None:
        """Tag an image with a new name."""
        message: str = "Docker engine tag_image is not yet implemented"
        raise NotImplementedError(message)

    def create_container(
        self,
        image: str,
        volumes: dict[str, str] | None = None,
    ) -> str:
        """Create a container from an image."""
        message: str = "Docker engine create_container is not yet implemented"
        raise NotImplementedError(message)

    def start_container_attached(
        self,
        identifier: str,
        timeout: int = 600,
    ) -> tuple[int, str, str]:
        """Start a container and wait for it to complete."""
        message: str = "Docker engine start_container_attached is not yet implemented"
        raise NotImplementedError(message)

    def copy_to_container(self, identifier: str, source: Path, destination: str) -> None:
        """Copy a file or directory to a container."""
        message: str = "Docker engine copy_to_container is not yet implemented"
        raise NotImplementedError(message)

    def copy_from_container(self, identifier: str, source: str, destination: Path) -> None:
        """Copy a file or directory from a container."""
        message: str = "Docker engine copy_from_container is not yet implemented"
        raise NotImplementedError(message)

    def remove_container(self, identifier: str, *, force: bool = False) -> None:
        """Remove a container."""
        message: str = "Docker engine remove_container is not yet implemented"
        raise NotImplementedError(message)

    def start_container(self, identifier: str) -> None:
        """Start a container without waiting for it to complete."""
        message: str = "Docker engine start_container is not yet implemented"
        raise NotImplementedError(message)

    def get_container_status(self, identifier: str) -> str:
        """Get the status of a container."""
        message: str = "Docker engine get_container_status is not yet implemented"
        raise NotImplementedError(message)

    def stop_container(self, identifier: str, timeout: int = 10) -> None:
        """Stop a running container gracefully."""
        message: str = "Docker engine stop_container is not yet implemented"
        raise NotImplementedError(message)

    def read_file_from_container(self, identifier: str, path: str) -> str:
        """Read a file from inside a running container using exec."""
        message: str = "Docker engine read_file_from_container is not yet implemented"
        raise NotImplementedError(message)

    def tail_file_from_container(self, identifier: str, path: str, start_line: int = 1) -> str:
        """Read a file from a container starting at a given line number."""
        message: str = "Docker engine tail_file_from_container is not yet implemented"
        raise NotImplementedError(message)

    def list_containers(self, all_containers: bool = True) -> list[dict]:
        """List containers."""
        message: str = "Docker engine list_containers is not yet implemented"
        raise NotImplementedError(message)

    def read_file_from_image(self, image: str, path: str) -> str:
        """Read a file from inside an image without starting a long-running container."""
        message: str = "Docker engine read_file_from_image is not yet implemented"
        raise NotImplementedError(message)
