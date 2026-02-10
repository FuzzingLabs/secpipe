from __future__ import annotations

import tarfile
from io import BytesIO
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, cast

from podman.errors import ImageNotFound

from fuzzforge_common.exceptions import FuzzForgeError
from fuzzforge_common.sandboxes.engines.base.engine import AbstractFuzzForgeSandboxEngine, ImageInfo

if TYPE_CHECKING:
    from podman import PodmanClient
    from podman.domain.containers import Container
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """TODO."""
    from structlog import get_logger  # noqa: PLC0415 (required by temporal)

    return cast("BoundLogger", get_logger())


class Podman(AbstractFuzzForgeSandboxEngine):
    """TODO."""

    #: TODO.
    __socket: str

    def __init__(self, socket: str) -> None:
        """Initialize an instance of the class.

        :param socket: TODO.

        """
        AbstractFuzzForgeSandboxEngine.__init__(self)
        self.__socket = socket

    def get_client(self) -> PodmanClient:
        """TODO.

        :returns TODO.

        """
        from podman import PodmanClient  # noqa: PLC0415 (required by temporal)

        return PodmanClient(base_url=self.__socket)

    def list_images(self, filter_prefix: str | None = None) -> list[ImageInfo]:
        """List available container images.

        :param filter_prefix: Optional prefix to filter images (e.g., "localhost/").
        :returns: List of ImageInfo objects for available images.

        """
        client: PodmanClient = self.get_client()
        images: list[ImageInfo] = []

        with client:
            for image in client.images.list():
                # Get all tags for this image
                tags = image.tags or []
                for tag in tags:
                    # Apply filter if specified
                    if filter_prefix and not tag.startswith(filter_prefix):
                        continue

                    # Parse repository and tag
                    if ":" in tag:
                        repo, tag_name = tag.rsplit(":", 1)
                    else:
                        repo = tag
                        tag_name = "latest"

                    images.append(
                        ImageInfo(
                            reference=tag,
                            repository=repo,
                            tag=tag_name,
                            image_id=image.short_id if hasattr(image, "short_id") else image.id[:12],
                            size=image.attrs.get("Size") if hasattr(image, "attrs") else None,
                        )
                    )

        get_logger().debug("listed images", count=len(images), filter_prefix=filter_prefix)
        return images

    def register_archive(self, archive: Path, repository: str) -> None:
        """TODO.

        :param archive: TODO.

        """
        client: PodmanClient = self.get_client()
        with client:
            images = list(client.images.load(file_path=archive))
        if len(images) != 1:
            message: str = "expected only one image"
            raise FuzzForgeError(message)
        image = images[0]
        image.tag(repository=repository, tag="latest")

    def spawn_sandbox(self, image: str) -> str:
        """Spawn a sandbox based on the given image.

        :param image: The image the sandbox should be based on.
        :returns: The sandbox identifier.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.create(image=image)
            container_identifier: str = container.id
            get_logger().debug("create podman container", container_identifier=container_identifier)
            return container_identifier

    def push_archive_to_sandbox(self, identifier: str, source: Path, destination: PurePath) -> None:
        """TODO.

        :param identifier: TODO.
        :param source: TODO.
        :param destination: TODO.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            get_logger().debug(
                "push archive to podman container",
                container_identifier=identifier,
                container_status=container.status,
            )
            # reading everything at once for now, even though this temporary solution is not viable with large files,
            # since the podman sdk does not currently expose a way to chunk uploads.
            # in order to fix this issue, we could directly interact with the podman rest api or make a contribution
            # to the podman sdk in order to allow the 'put_archive' method to support chunked uploads.
            data: bytes = source.read_bytes()
            container.put_archive(path=str(destination), data=data)

    def start_sandbox(self, identifier: str) -> None:
        """Start the sandbox matching the given identifier.

        :param identifier: The identifier of the sandbox to start.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            get_logger().debug(
                "start podman container",
                container_identifier=identifier,
                container_status=container.status,
            )
            container.start()

    def execute_inside_sandbox(self, identifier: str, command: list[str]) -> None:
        """Execute a command inside the sandbox matching the given identifier and wait for completion.

        :param sandbox: The identifier of the sandbox.
        :param command: The command to run.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            get_logger().debug(
                "executing command inside podman container",
                container_identifier=identifier,
                container_status=container.status,
            )
            (status, (stdout, stderr)) = container.exec_run(cmd=command, demux=True)
            get_logger().debug(
                "command execution result",
                status=status,
                stdout_size=len(stdout) if stdout else 0,
                stderr_size=len(stderr) if stderr else 0,
            )

    def pull_archive_from_sandbox(self, identifier: str, source: PurePath) -> Path:
        """TODO.

        :param identifier: TODO.
        :param source: TODO.
        :returns: TODO.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            get_logger().debug(
                "pull archive from podman container",
                container_identifier=identifier,
                container_status=container.status,
            )
            with NamedTemporaryFile(delete=False, delete_on_close=False) as file:
                stream, _stat = container.get_archive(path=str(source))
                for chunk in stream:
                    file.write(chunk)
            get_logger().debug(
                "created archive",
                archive=file.name,
            )
            return Path(file.name)

    def terminate_sandbox(self, identifier: str) -> None:
        """Terminate the sandbox matching the given identifier.

        :param identifier: The identifier of the sandbox to terminate.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            get_logger().debug(
                "kill podman container",
                container_identifier=identifier,
                container_status=container.status,
            )
            # Only kill running containers; for created/stopped, skip to remove
            if container.status in ("running", "paused"):
                container.kill()
            get_logger().debug(
                "remove podman container",
                container_identifier=identifier,
                container_status=container.status,
            )
            container.remove()

    # -------------------------------------------------------------------------
    # Extended Container Operations
    # -------------------------------------------------------------------------

    def image_exists(self, image: str) -> bool:
        """Check if a container image exists locally.

        :param image: Full image reference (e.g., "localhost/module:latest").
        :returns: True if image exists, False otherwise.

        """
        client: PodmanClient = self.get_client()
        with client:
            try:
                client.images.get(name=image)
            except ImageNotFound:
                return False
            else:
                return True

    def pull_image(self, image: str, timeout: int = 300) -> None:
        """Pull an image from a container registry.

        :param image: Full image reference to pull.
        :param timeout: Timeout in seconds for the pull operation.
        :raises FuzzForgeError: If pull fails.

        """
        client: PodmanClient = self.get_client()
        with client:
            try:
                get_logger().info("pulling image", image=image)
                client.images.pull(repository=image)
                get_logger().info("image pulled successfully", image=image)
            except Exception as exc:
                message = f"Failed to pull image '{image}': {exc}"
                raise FuzzForgeError(message) from exc

    def tag_image(self, source: str, target: str) -> None:
        """Tag an image with a new name.

        :param source: Source image reference.
        :param target: Target image reference.

        """
        client: PodmanClient = self.get_client()
        with client:
            image = client.images.get(name=source)
            # Parse target into repository and tag
            if ":" in target:
                repo, tag = target.rsplit(":", 1)
            else:
                repo = target
                tag = "latest"
            image.tag(repository=repo, tag=tag)
            get_logger().debug("tagged image", source=source, target=target)

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
        client: PodmanClient = self.get_client()
        with client:
            # Build volume mounts in podman format
            mounts = []
            if volumes:
                for host_path, container_path in volumes.items():
                    mounts.append({"type": "bind", "source": host_path, "target": container_path, "read_only": True})

            container: Container = client.containers.create(image=image, mounts=mounts if mounts else None)
            container_id: str = str(container.id)
            get_logger().debug("created container", container_id=container_id, image=image)
            return container_id

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
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            get_logger().debug("starting container attached", container_id=identifier)

            # Start the container
            container.start()

            # Wait for completion with timeout
            result = container.wait(timeout=timeout)
            exit_code: int = result.get("StatusCode", -1) if isinstance(result, dict) else int(result)

            # Get logs
            stdout_raw = container.logs(stdout=True, stderr=False)
            stderr_raw = container.logs(stdout=False, stderr=True)

            # Decode if bytes
            stdout_str: str = ""
            stderr_str: str = ""
            if isinstance(stdout_raw, bytes):
                stdout_str = stdout_raw.decode("utf-8", errors="replace")
            elif isinstance(stdout_raw, str):
                stdout_str = stdout_raw
            if isinstance(stderr_raw, bytes):
                stderr_str = stderr_raw.decode("utf-8", errors="replace")
            elif isinstance(stderr_raw, str):
                stderr_str = stderr_raw

            get_logger().debug("container finished", container_id=identifier, exit_code=exit_code)
            return (exit_code, stdout_str, stderr_str)

    def copy_to_container(self, identifier: str, source: Path, destination: str) -> None:
        """Copy a file or directory to a container.

        :param identifier: Container identifier.
        :param source: Source path on host.
        :param destination: Destination path in container.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)

            # Create tar archive in memory
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                tar.add(str(source), arcname=Path(source).name)
            tar_buffer.seek(0)

            # Use put_archive to copy
            container.put_archive(path=destination, data=tar_buffer.read())
            get_logger().debug("copied to container", source=str(source), destination=destination)

    def copy_from_container(self, identifier: str, source: str, destination: Path) -> None:
        """Copy a file or directory from a container.

        :param identifier: Container identifier.
        :param source: Source path in container.
        :param destination: Destination path on host.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)

            # Get archive from container
            stream, _stat = container.get_archive(path=source)

            # Write to temp file and extract
            tar_buffer = BytesIO()
            for chunk in stream:
                tar_buffer.write(chunk)
            tar_buffer.seek(0)

            # Extract to destination
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                tar.extractall(path=destination)  # noqa: S202 (trusted source)

            get_logger().debug("copied from container", source=source, destination=str(destination))

    def remove_container(self, identifier: str, *, force: bool = False) -> None:
        """Remove a container.

        :param identifier: Container identifier.
        :param force: Force removal even if running.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            if force and container.status in ("running", "paused"):
                container.kill()
            container.remove()
            get_logger().debug("removed container", container_id=identifier)

    def start_container(self, identifier: str) -> None:
        """Start a container without waiting for it to complete.

        :param identifier: Container identifier.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            container.start()
            get_logger().debug("started container (detached)", container_id=identifier)

    def get_container_status(self, identifier: str) -> str:
        """Get the status of a container.

        :param identifier: Container identifier.
        :returns: Container status (e.g., "running", "exited", "created").

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            return str(container.status)

    def stop_container(self, identifier: str, timeout: int = 10) -> None:
        """Stop a running container gracefully.

        :param identifier: Container identifier.
        :param timeout: Seconds to wait before killing.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            if container.status == "running":
                container.stop(timeout=timeout)
            get_logger().debug("stopped container", container_id=identifier)

    def read_file_from_container(self, identifier: str, path: str) -> str:
        """Read a file from inside a running container using exec.

        :param identifier: Container identifier.
        :param path: Path to file inside container.
        :returns: File contents as string.

        """
        client: PodmanClient = self.get_client()
        with client:
            container: Container = client.containers.get(key=identifier)
            (status, (stdout, stderr)) = container.exec_run(cmd=["cat", path], demux=True)
            if status != 0:
                error_msg = stderr.decode("utf-8", errors="replace") if stderr else "File not found"
                get_logger().debug("failed to read file from container", path=path, error=error_msg)
                return ""
            return stdout.decode("utf-8", errors="replace") if stdout else ""

    def list_containers(self, all_containers: bool = True) -> list[dict]:
        """List containers.

        :param all_containers: Include stopped containers.
        :returns: List of container info dicts.

        """
        client: PodmanClient = self.get_client()
        with client:
            containers = client.containers.list(all=all_containers)
            return [
                {
                    "Id": str(c.id),
                    "Names": [c.name] if hasattr(c, "name") else [],
                    "Status": str(c.status),
                    "Image": str(c.image) if hasattr(c, "image") else "",
                }
                for c in containers
            ]

    def read_file_from_image(self, image: str, path: str) -> str:
        """Read a file from inside an image without starting a long-running container.

        Creates a temporary container, reads the file, and removes the container.

        :param image: Image reference (e.g., "fuzzforge-rust-analyzer:latest").
        :param path: Path to file inside image.
        :returns: File contents as string.

        """
        logger = get_logger()
        client: PodmanClient = self.get_client()
        
        with client:
            try:
                # Create a container that just runs cat on the file
                container = client.containers.create(
                    image=image,
                    command=["cat", path],
                    remove=True,
                )
                
                # Start it and wait for completion
                container.start()
                container.wait()
                
                # Get the logs (which contain stdout)
                output = container.logs(stdout=True, stderr=False)
                
                if isinstance(output, bytes):
                    return output.decode("utf-8", errors="replace")
                return str(output)
                
            except Exception as exc:
                logger.debug("failed to read file from image", image=image, path=path, error=str(exc))
                return ""
