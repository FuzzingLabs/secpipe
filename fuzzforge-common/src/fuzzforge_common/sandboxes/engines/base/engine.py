from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path, PurePath


@dataclass
class ImageInfo:
    """Information about a container image."""

    #: Full image reference (e.g., "localhost/fuzzforge-module-echidna:latest").
    reference: str

    #: Repository name (e.g., "localhost/fuzzforge-module-echidna").
    repository: str

    #: Image tag (e.g., "latest").
    tag: str

    #: Image ID (short hash).
    image_id: str | None = None

    #: Image size in bytes.
    size: int | None = None

    #: Image labels/metadata.
    labels: dict[str, str] | None = None


class AbstractFuzzForgeSandboxEngine(ABC):
    """Abstract class used as a base for all FuzzForge sandbox engine classes."""

    @abstractmethod
    def list_images(self, filter_prefix: str | None = None) -> list[ImageInfo]:
        """List available container images.

        :param filter_prefix: Optional prefix to filter images (e.g., "localhost/").
        :returns: List of ImageInfo objects for available images.

        """
        message: str = f"method 'list_images' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def register_archive(self, archive: Path, repository: str) -> None:
        """TODO.

        :param archive: TODO.

        """
        message: str = f"method 'register_archive' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def spawn_sandbox(self, image: str) -> str:
        """Spawn a sandbox based on the given image.

        :param image: The image the sandbox should be based on.
        :returns: The sandbox identifier.

        """
        message: str = f"method 'spawn_sandbox' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def push_archive_to_sandbox(self, identifier: str, source: Path, destination: PurePath) -> None:
        """TODO.

        :param identifier: TODO.
        :param source: TODO.
        :param destination: TODO.

        """
        message: str = f"method 'push_archive_to_sandbox' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def start_sandbox(self, identifier: str) -> None:
        """TODO.

        :param identifier: The identifier of the sandbox to start.

        """
        message: str = f"method 'start_sandbox' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def execute_inside_sandbox(self, identifier: str, command: list[str]) -> None:
        """Execute a command inside the sandbox matching the given identifier and wait for completion.

        :param sandbox: The identifier of the sandbox.
        :param command: The command to run.

        """
        message: str = f"method 'execute_inside_sandbox' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def pull_archive_from_sandbox(self, identifier: str, source: PurePath) -> Path:
        """TODO.

        :param identifier: TODO.
        :param source: TODO.
        :returns: TODO.

        """
        message: str = f"method 'pull_archive_from_sandbox' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def terminate_sandbox(self, identifier: str) -> None:
        """Terminate the sandbox matching the given identifier.

        :param identifier: The identifier of the sandbox to terminate.

        """
        message: str = f"method 'terminate_sandbox' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    # -------------------------------------------------------------------------
    # Extended Container Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    def image_exists(self, image: str) -> bool:
        """Check if a container image exists locally.

        :param image: Full image reference (e.g., "localhost/module:latest").
        :returns: True if image exists, False otherwise.

        """
        message: str = f"method 'image_exists' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def pull_image(self, image: str, timeout: int = 300) -> None:
        """Pull an image from a container registry.

        :param image: Full image reference to pull.
        :param timeout: Timeout in seconds for the pull operation.
        :raises FuzzForgeError: If pull fails.

        """
        message: str = f"method 'pull_image' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def tag_image(self, source: str, target: str) -> None:
        """Tag an image with a new name.

        :param source: Source image reference.
        :param target: Target image reference.

        """
        message: str = f"method 'tag_image' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def create_container(
        self,
        image: str,
        volumes: dict[str, str] | None = None,
    ) -> str:
        """Create a container from an image.

        :param image: Image to create container from.
        :param volumes: Optional volume mappings {host_path: container_path}.
        :returns: Container identifier.

        """
        message: str = f"method 'create_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def start_container_attached(
        self,
        identifier: str,
        timeout: int = 600,
    ) -> tuple[int, str, str]:
        """Start a container and wait for it to complete.

        :param identifier: Container identifier.
        :param timeout: Timeout in seconds for execution.
        :returns: Tuple of (exit_code, stdout, stderr).

        """
        message: str = f"method 'start_container_attached' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def copy_to_container(self, identifier: str, source: Path, destination: str) -> None:
        """Copy a file or directory to a container.

        :param identifier: Container identifier.
        :param source: Source path on host.
        :param destination: Destination path in container.

        """
        message: str = f"method 'copy_to_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def copy_from_container(self, identifier: str, source: str, destination: Path) -> None:
        """Copy a file or directory from a container.

        :param identifier: Container identifier.
        :param source: Source path in container.
        :param destination: Destination path on host.

        """
        message: str = f"method 'copy_from_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def remove_container(self, identifier: str, *, force: bool = False) -> None:
        """Remove a container.

        :param identifier: Container identifier.
        :param force: Force removal even if running.

        """
        message: str = f"method 'remove_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    # -------------------------------------------------------------------------
    # Continuous/Background Execution Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    def start_container(self, identifier: str) -> None:
        """Start a container without waiting for it to complete (detached mode).

        :param identifier: Container identifier.

        """
        message: str = f"method 'start_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def get_container_status(self, identifier: str) -> str:
        """Get the status of a container.

        :param identifier: Container identifier.
        :returns: Container status (e.g., "running", "exited", "created").

        """
        message: str = f"method 'get_container_status' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def stop_container(self, identifier: str, timeout: int = 10) -> None:
        """Stop a running container gracefully.

        :param identifier: Container identifier.
        :param timeout: Seconds to wait before killing.

        """
        message: str = f"method 'stop_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def read_file_from_container(self, identifier: str, path: str) -> str:
        """Read a file from inside a running container using exec.

        :param identifier: Container identifier.
        :param path: Path to file inside container.
        :returns: File contents as string.

        """
        message: str = f"method 'read_file_from_container' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def list_containers(self, all_containers: bool = True) -> list[dict]:
        """List containers.

        :param all_containers: Include stopped containers.
        :returns: List of container info dicts.

        """
        message: str = f"method 'list_containers' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def read_file_from_image(self, image: str, path: str) -> str:
        """Read a file from inside an image without starting a container.

        Creates a temporary container, copies the file, and removes the container.

        :param image: Image reference (e.g., "fuzzforge-rust-analyzer:latest").
        :param path: Path to file inside image.
        :returns: File contents as string.

        """
        message: str = f"method 'read_file_from_image' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)
