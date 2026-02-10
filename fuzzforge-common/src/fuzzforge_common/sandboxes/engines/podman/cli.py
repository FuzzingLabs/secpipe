"""Podman CLI engine with custom storage support.

This engine uses subprocess calls to the Podman CLI instead of the socket API,
allowing for custom storage paths (--root, --runroot) that work regardless of
system Podman configuration or snap environment issues.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, cast

from fuzzforge_common.exceptions import FuzzForgeError
from fuzzforge_common.sandboxes.engines.base.engine import AbstractFuzzForgeSandboxEngine, ImageInfo

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structured logger."""
    from structlog import get_logger  # noqa: PLC0415 (required by temporal)

    return cast("BoundLogger", get_logger())


def _is_running_under_snap() -> bool:
    """Check if running under Snap environment.

    VS Code installed via Snap sets XDG_DATA_HOME to a version-specific path,
    causing Podman to look for storage in non-standard locations. When SNAP
    is set, we use custom storage paths to ensure consistency.

    Note: Snap only exists on Linux, so this also handles macOS implicitly.
    """
    import os  # noqa: PLC0415

    return os.getenv("SNAP") is not None


class PodmanCLI(AbstractFuzzForgeSandboxEngine):
    """Podman engine using CLI with custom storage paths.

    This implementation uses subprocess calls to the Podman CLI with --root
    and --runroot flags when running under Snap, providing isolation from
    system Podman storage.

    The custom storage is only used when:
    1. Running under Snap (SNAP env var is set) - to fix XDG_DATA_HOME issues
    2. Custom paths are explicitly provided

    Otherwise, uses default Podman storage which works for:
    - Native Linux installations
    - macOS (where Podman runs in a VM via podman machine)
    """

    __graphroot: Path | None
    __runroot: Path | None
    __use_custom_storage: bool

    def __init__(self, graphroot: Path | None = None, runroot: Path | None = None) -> None:
        """Initialize the PodmanCLI engine.

        :param graphroot: Path to container image storage.
        :param runroot: Path to container runtime state.

        Custom storage is used when running under Snap AND paths are provided.

        :raises FuzzForgeError: If running on macOS (Podman not supported).
        """
        import sys  # noqa: PLC0415

        if sys.platform == "darwin":
            msg = (
                "Podman is not supported on macOS. Please use Docker instead:\n"
                "  brew install --cask docker\n"
                "  # Or download from https://docker.com/products/docker-desktop"
            )
            raise FuzzForgeError(msg)

        AbstractFuzzForgeSandboxEngine.__init__(self)

        # Use custom storage only under Snap (to fix XDG_DATA_HOME issues)
        self.__use_custom_storage = _is_running_under_snap() and graphroot is not None and runroot is not None

        if self.__use_custom_storage:
            self.__graphroot = graphroot
            self.__runroot = runroot
            # Ensure directories exist
            self.__graphroot.mkdir(parents=True, exist_ok=True)
            self.__runroot.mkdir(parents=True, exist_ok=True)
        else:
            self.__graphroot = None
            self.__runroot = None

    def _base_cmd(self) -> list[str]:
        """Get base Podman command with storage flags.

        :returns: Base command list, with --root and --runroot only under Snap.

        """
        if self.__use_custom_storage and self.__graphroot and self.__runroot:
            return [
                "podman",
                "--root",
                str(self.__graphroot),
                "--runroot",
                str(self.__runroot),
            ]
        return ["podman"]

    def _run(self, args: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
        """Run a Podman command.

        :param args: Command arguments (without 'podman').
        :param check: Raise exception on non-zero exit.
        :param capture: Capture stdout/stderr.
        :returns: CompletedProcess result.

        """
        cmd = self._base_cmd() + args
        get_logger().debug("running podman command", cmd=" ".join(cmd))
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
            data = json.loads(result.stdout) if result.stdout.strip() else []
        except json.JSONDecodeError:
            get_logger().warning("failed to parse podman images output")
            return images

        for image in data:
            # Get repository and tag from Names
            names = image.get("Names") or []
            for name in names:
                if filter_prefix and not name.startswith(filter_prefix):
                    continue

                # Parse repository and tag
                if ":" in name:
                    repo, tag = name.rsplit(":", 1)
                else:
                    repo = name
                    tag = "latest"

                # Get labels if available
                labels = image.get("Labels") or {}

                images.append(
                    ImageInfo(
                        reference=name,
                        repository=repo,
                        tag=tag,
                        image_id=image.get("Id", "")[:12],
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
        result = self._run(["image", "exists", image], check=False)
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
            raise FuzzForgeError(message) from exc

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
        # Parse loaded image ID from output
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
            data = json.loads(result.stdout) if result.stdout.strip() else []
            # Handle both list and single object responses
            if isinstance(data, dict):
                data = [data]
            return [
                {
                    "Id": c.get("Id", ""),
                    "Names": c.get("Names", []),
                    "Status": c.get("State", ""),
                    "Image": c.get("Image", ""),
                }
                for c in data
            ]
        except json.JSONDecodeError:
            return []

    def read_file_from_image(self, image: str, path: str) -> str:
        """Read a file from inside an image without starting a long-running container.

        Creates a temporary container, reads the file via cat, and removes it.

        :param image: Image reference (e.g., "fuzzforge-rust-analyzer:latest").
        :param path: Path to file inside image.
        :returns: File contents as string.

        """
        logger = get_logger()
        
        # Create a temporary container (don't start it)
        create_result = self._run(
            ["create", "--rm", image, "cat", path],
            check=False,
        )
        
        if create_result.returncode != 0:
            logger.debug("failed to create container for file read", image=image, path=path)
            return ""
        
        container_id = create_result.stdout.strip()
        
        try:
            # Start the container and capture output (cat will run and exit)
            start_result = self._run(
                ["start", "-a", container_id],
                check=False,
            )
            
            if start_result.returncode != 0:
                logger.debug("failed to read file from image", image=image, path=path)
                return ""
            
            return start_result.stdout
        finally:
            # Cleanup: remove the container (may already be removed due to --rm)
            self._run(["rm", "-f", container_id], check=False)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_storage_info(self) -> dict:
        """Get storage configuration info.

        :returns: Dict with graphroot and runroot paths.

        """
        return {
            "graphroot": str(self.__graphroot),
            "runroot": str(self.__runroot),
        }
