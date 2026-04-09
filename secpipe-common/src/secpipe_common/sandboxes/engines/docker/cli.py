"""Docker CLI engine.

This engine uses subprocess calls to the Docker CLI, providing a simple
and portable interface that works on Linux, macOS, and Windows wherever
Docker Desktop or Docker Engine is installed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, cast

from secpipe_common.exceptions import SecPipeError
from secpipe_common.sandboxes.engines.base.engine import AbstractSecPipeSandboxEngine, ImageInfo

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structured logger."""
    from structlog import get_logger  # noqa: PLC0415 (required by temporal)

    return cast("BoundLogger", get_logger())


class DockerCLI(AbstractSecPipeSandboxEngine):
    """Docker engine using CLI commands.

    This implementation uses subprocess calls to the Docker CLI,
    providing a simple and portable interface that works wherever
    Docker is installed (Docker Desktop on macOS/Windows, Docker Engine on Linux).
    """

    def __init__(self) -> None:
        """Initialize the DockerCLI engine."""
        AbstractSecPipeSandboxEngine.__init__(self)

    def _base_cmd(self) -> list[str]:
        """Get base Docker command.

        :returns: Base command list.

        """
        return ["docker"]

    def _run(self, args: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
        """Run a Docker command.

        :param args: Command arguments (without 'docker').
        :param check: Raise exception on non-zero exit.
        :param capture: Capture stdout/stderr.
        :returns: CompletedProcess result.

        """
        cmd = self._base_cmd() + args
        get_logger().debug("running docker command", cmd=" ".join(cmd))
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
        )

    # -------------------------------------------------------------------------
    # Image Operations
    # -------------------------------------------------------------------------

    def list_images(self, filter_prefix: str | None = None) -> list[ImageInfo]:
        """List available container images.

        :param filter_prefix: Optional prefix to filter images.
        :returns: List of ImageInfo objects.

        """
        result = self._run(["images", "--format", "json"])
        images: list[ImageInfo] = []

        try:
            # Docker outputs one JSON object per line
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            data = [json.loads(line) for line in lines if line.strip()]
        except json.JSONDecodeError:
            get_logger().warning("failed to parse docker images output")
            return images

        for image in data:
            repo = image.get("Repository", "")
            tag = image.get("Tag", "latest")
            
            if repo == "<none>":
                continue
                
            reference = f"{repo}:{tag}"

            if filter_prefix and filter_prefix not in reference:
                continue

            # Try to get labels from image inspect
            labels = {}
            try:
                inspect_result = self._run(["image", "inspect", reference], check=False)
                if inspect_result.returncode == 0:
                    inspect_data = json.loads(inspect_result.stdout)
                    if inspect_data and len(inspect_data) > 0:
                        labels = inspect_data[0].get("Config", {}).get("Labels") or {}
            except (json.JSONDecodeError, IndexError):
                pass

            images.append(
                ImageInfo(
                    reference=reference,
                    repository=repo,
                    tag=tag,
                    image_id=image.get("ID", "")[:12],
                    size=image.get("Size"),
                    labels=labels,
                )
            )

        get_logger().debug("listed images", count=len(images), filter_prefix=filter_prefix)
        return images

    def image_exists(self, image: str) -> bool:
        """Check if a container image exists locally.

        :param image: Full image reference.
        :returns: True if image exists.

        """
        result = self._run(["image", "inspect", image], check=False)
        return result.returncode == 0

    def pull_image(self, image: str, timeout: int = 300) -> None:
        """Pull an image from a container registry.

        :param image: Full image reference.
        :param timeout: Timeout in seconds.

        """
        get_logger().info("pulling image", image=image)
        try:
            self._run(["pull", image])
            get_logger().info("image pulled successfully", image=image)
        except subprocess.CalledProcessError as exc:
            message = f"Failed to pull image '{image}': {exc.stderr}"
            raise SecPipeError(message) from exc

    def tag_image(self, source: str, target: str) -> None:
        """Tag an image with a new name.

        :param source: Source image reference.
        :param target: Target image reference.

        """
        self._run(["tag", source, target])
        get_logger().debug("tagged image", source=source, target=target)

    def build_image(self, context_path: Path, tag: str, dockerfile: str = "Dockerfile") -> None:
        """Build an image from a Dockerfile.

        :param context_path: Path to build context.
        :param tag: Image tag.
        :param dockerfile: Dockerfile name.

        """
        get_logger().info("building image", tag=tag, context=str(context_path))
        self._run(["build", "-t", tag, "-f", dockerfile, str(context_path)])
        get_logger().info("image built successfully", tag=tag)

    def register_archive(self, archive: Path, repository: str) -> None:
        """Load an image from a tar archive.

        :param archive: Path to tar archive.
        :param repository: Repository name for the loaded image.

        """
        result = self._run(["load", "-i", str(archive)])
        # Tag the loaded image
        for line in result.stdout.splitlines():
            if "Loaded image:" in line:
                loaded_image = line.split("Loaded image:")[-1].strip()
                self._run(["tag", loaded_image, f"{repository}:latest"])
                break
        get_logger().debug("registered archive", archive=str(archive), repository=repository)

    # -------------------------------------------------------------------------
    # Container Operations
    # -------------------------------------------------------------------------

    def spawn_sandbox(self, image: str) -> str:
        """Spawn a sandbox (container) from an image.

        :param image: Image to create container from.
        :returns: Container identifier.

        """
        result = self._run(["create", image])
        container_id = result.stdout.strip()
        get_logger().debug("created container", container_id=container_id)
        return container_id

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
        args = ["create"]
        if volumes:
            for host_path, container_path in volumes.items():
                args.extend(["-v", f"{host_path}:{container_path}:ro"])
        args.append(image)

        result = self._run(args)
        container_id = result.stdout.strip()
        get_logger().debug("created container", container_id=container_id, image=image)
        return container_id

    def start_sandbox(self, identifier: str) -> None:
        """Start a container.

        :param identifier: Container identifier.

        """
        self._run(["start", identifier])
        get_logger().debug("started container", container_id=identifier)

    def start_container(self, identifier: str) -> None:
        """Start a container without waiting.

        :param identifier: Container identifier.

        """
        self._run(["start", identifier])
        get_logger().debug("started container (detached)", container_id=identifier)

    def start_container_attached(
        self,
        identifier: str,
        timeout: int = 600,
    ) -> tuple[int, str, str]:
        """Start a container and wait for completion.

        :param identifier: Container identifier.
        :param timeout: Timeout in seconds.
        :returns: Tuple of (exit_code, stdout, stderr).

        """
        get_logger().debug("starting container attached", container_id=identifier)
        # Start the container
        self._run(["start", identifier])

        # Wait for completion
        wait_result = self._run(["wait", identifier])
        exit_code = int(wait_result.stdout.strip()) if wait_result.stdout.strip() else -1

        # Get logs
        stdout_result = self._run(["logs", identifier], check=False)
        stdout_str = stdout_result.stdout or ""
        stderr_str = stdout_result.stderr or ""

        get_logger().debug("container finished", container_id=identifier, exit_code=exit_code)
        return (exit_code, stdout_str, stderr_str)

    def execute_inside_sandbox(self, identifier: str, command: list[str]) -> None:
        """Execute a command inside a container.

        :param identifier: Container identifier.
        :param command: Command to run.

        """
        get_logger().debug("executing command in container", container_id=identifier)
        self._run(["exec", identifier] + command)

    def push_archive_to_sandbox(self, identifier: str, source: Path, destination: PurePath) -> None:
        """Copy an archive to a container.

        :param identifier: Container identifier.
        :param source: Source archive path.
        :param destination: Destination path in container.

        """
        get_logger().debug("copying to container", container_id=identifier, source=str(source))
        self._run(["cp", str(source), f"{identifier}:{destination}"])

    def pull_archive_from_sandbox(self, identifier: str, source: PurePath) -> Path:
        """Copy files from a container to a local archive.

        :param identifier: Container identifier.
        :param source: Source path in container.
        :returns: Path to local archive.

        """
        get_logger().debug("copying from container", container_id=identifier, source=str(source))
        with NamedTemporaryFile(delete=False, delete_on_close=False, suffix=".tar") as tmp:
            self._run(["cp", f"{identifier}:{source}", tmp.name])
            return Path(tmp.name)

    def copy_to_container(self, identifier: str, source: Path, destination: str) -> None:
        """Copy a file or directory to a container.

        :param identifier: Container identifier.
        :param source: Source path on host.
        :param destination: Destination path in container.

        """
        self._run(["cp", str(source), f"{identifier}:{destination}"])
        get_logger().debug("copied to container", source=str(source), destination=destination)

    def copy_from_container(self, identifier: str, source: str, destination: Path) -> None:
        """Copy a file or directory from a container.

        :param identifier: Container identifier.
        :param source: Source path in container.
        :param destination: Destination path on host.

        """
        destination.mkdir(parents=True, exist_ok=True)
        self._run(["cp", f"{identifier}:{source}", str(destination)])
        get_logger().debug("copied from container", source=source, destination=str(destination))

    def terminate_sandbox(self, identifier: str) -> None:
        """Terminate and remove a container.

        :param identifier: Container identifier.

        """
        # Stop if running
        self._run(["stop", identifier], check=False)
        # Remove
        self._run(["rm", "-f", identifier], check=False)
        get_logger().debug("terminated container", container_id=identifier)

    def remove_container(self, identifier: str, *, force: bool = False) -> None:
        """Remove a container.

        :param identifier: Container identifier.
        :param force: Force removal.

        """
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(identifier)
        self._run(args, check=False)
        get_logger().debug("removed container", container_id=identifier)

    def stop_container(self, identifier: str, timeout: int = 10) -> None:
        """Stop a running container.

        :param identifier: Container identifier.
        :param timeout: Seconds to wait before killing.

        """
        self._run(["stop", "-t", str(timeout), identifier], check=False)
        get_logger().debug("stopped container", container_id=identifier)

    def get_container_status(self, identifier: str) -> str:
        """Get the status of a container.

        :param identifier: Container identifier.
        :returns: Container status.

        """
        result = self._run(["inspect", "--format", "{{.State.Status}}", identifier], check=False)
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    def read_file_from_container(self, identifier: str, path: str) -> str:
        """Read a file from inside a container.

        :param identifier: Container identifier.
        :param path: Path to file in container.
        :returns: File contents.

        """
        result = self._run(["exec", identifier, "cat", path], check=False)
        if result.returncode != 0:
            get_logger().debug("failed to read file from container", path=path)
            return ""
        return result.stdout

    def tail_file_from_container(self, identifier: str, path: str, start_line: int = 1) -> str:
        """Read a file from a container starting at a given line number.

        :param identifier: Container identifier.
        :param path: Path to file in container.
        :param start_line: 1-based line number to start reading from.
        :returns: File contents from *start_line* onwards.

        """
        result = self._run(
            ["exec", identifier, "tail", "-n", f"+{start_line}", path],
            check=False,
        )
        if result.returncode != 0:
            get_logger().debug("failed to tail file from container", path=path, start_line=start_line)
            return ""
        return result.stdout

    def list_containers(self, all_containers: bool = True) -> list[dict]:
        """List containers.

        :param all_containers: Include stopped containers.
        :returns: List of container info dicts.

        """
        args = ["ps", "--format", "json"]
        if all_containers:
            args.append("-a")

        result = self._run(args)
        try:
            # Docker outputs one JSON object per line
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            data = [json.loads(line) for line in lines if line.strip()]
            return [
                {
                    "Id": c.get("ID", ""),
                    "Names": c.get("Names", ""),
                    "Status": c.get("State", ""),
                    "Image": c.get("Image", ""),
                }
                for c in data
            ]
        except json.JSONDecodeError:
            return []

    def read_file_from_image(self, image: str, path: str) -> str:
        """Read a file from inside an image without starting a long-running container.

        Uses docker run with --entrypoint override to read the file via cat.

        :param image: Image reference (e.g., "secpipe-rust-analyzer:latest").
        :param path: Path to file inside image.
        :returns: File contents as string.

        """
        logger = get_logger()
        
        # Use docker run with --entrypoint to override any container entrypoint
        result = self._run(
            ["run", "--rm", "--entrypoint", "cat", image, path],
            check=False,
        )
        
        if result.returncode != 0:
            logger.debug("failed to read file from image", image=image, path=path, stderr=result.stderr)
            return ""
        
        return result.stdout
