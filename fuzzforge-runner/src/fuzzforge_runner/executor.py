"""FuzzForge Runner - Direct module execution engine.

This module provides direct execution of FuzzForge modules without
requiring Temporal workflow orchestration. It's designed for local
development and OSS deployment scenarios.

"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path, PurePath
from tarfile import TarFile, TarInfo
from tarfile import open as Archive  # noqa: N812
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TYPE_CHECKING, Any, cast

from fuzzforge_common.sandboxes.engines.docker.configuration import DockerConfiguration
from fuzzforge_common.sandboxes.engines.podman.configuration import PodmanConfiguration
from fuzzforge_types.executions import FuzzForgeExecutionIdentifier

from fuzzforge_runner.constants import (
    MODULE_ENTRYPOINT,
    RESULTS_ARCHIVE_FILENAME,
    SANDBOX_INPUT_DIRECTORY,
    SANDBOX_OUTPUT_DIRECTORY,
)
from fuzzforge_runner.exceptions import ModuleExecutionError, SandboxError

if TYPE_CHECKING:
    from fuzzforge_common.sandboxes.engines.base.engine import AbstractFuzzForgeSandboxEngine
    from fuzzforge_runner.settings import EngineSettings, Settings
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


class ModuleExecutor:
    """Direct executor for FuzzForge modules.

    Handles the complete lifecycle of module execution:
    - Spawning isolated sandbox containers
    - Pushing input assets and configuration
    - Running the module
    - Pulling output results
    - Cleanup

    """

    #: Full settings including engine and registry.
    _settings: Settings
    #: Engine settings for container operations.
    _engine_settings: EngineSettings

    def __init__(self, settings: Settings) -> None:
        """Initialize an instance of the class.

        :param settings: FuzzForge runner settings.

        """
        self._settings = settings
        self._engine_settings = settings.engine

    def _get_engine_configuration(self) -> DockerConfiguration | PodmanConfiguration:
        """Get the appropriate engine configuration.

        :returns: Engine configuration based on settings.

        Note: This is only used when socket mode is explicitly needed.
        The default is now PodmanCLI with custom storage paths.

        """
        from fuzzforge_common.sandboxes.engines.enumeration import FuzzForgeSandboxEngines

        # Ensure socket has proper scheme
        socket = self._engine_settings.socket
        if not socket.startswith(("unix://", "tcp://", "http://", "ssh://")):
            socket = f"unix://{socket}"

        if self._engine_settings.type == "docker":
            return DockerConfiguration(
                kind=FuzzForgeSandboxEngines.DOCKER,
                socket=socket,
            )
        return PodmanConfiguration(
            kind=FuzzForgeSandboxEngines.PODMAN,
            socket=socket,
        )

    def _get_engine(self) -> AbstractFuzzForgeSandboxEngine:
        """Get the container engine instance.

        Uses DockerCLI by default for simplicity (works on Linux, macOS, Windows).
        PodmanCLI is used when engine type is set to 'podman'.

        :returns: Configured container engine.

        """
        from fuzzforge_common.sandboxes.engines.docker import DockerCLI
        from fuzzforge_common.sandboxes.engines.podman import PodmanCLI

        # Use PodmanCLI for Podman (with custom storage under Snap)
        if self._engine_settings.type == "podman":
            return PodmanCLI(
                graphroot=self._engine_settings.graphroot,
                runroot=self._engine_settings.runroot,
            )

        # Use DockerCLI for Docker (default)
        return DockerCLI()

    def _check_image_exists(self, module_identifier: str) -> bool:
        """Check if a module image exists locally.

        :param module_identifier: Name/identifier of the module image.
        :returns: True if image exists, False otherwise.

        """
        engine = self._get_engine()

        # Try common tags
        tags_to_check = ["latest", "0.1.0", "0.0.1"]

        # Try multiple naming conventions:
        # - fuzzforge-{name}:{tag} (OSS local builds)
        # - fuzzforge-module-{name}:{tag} (OSS local builds with module prefix)
        # - localhost/fuzzforge-module-{name}:{tag} (standard convention)
        # - localhost/{name}:{tag} (legacy/short form)

        # For OSS local builds (no localhost/ prefix)
        for tag in tags_to_check:
            # Check direct module name (fuzzforge-cargo-fuzzer:0.1.0)
            if engine.image_exists(f"{module_identifier}:{tag}"):
                return True
            # Check with fuzzforge- prefix if not already present
            if not module_identifier.startswith("fuzzforge-"):
                if engine.image_exists(f"fuzzforge-{module_identifier}:{tag}"):
                    return True

        # For registry-style naming (localhost/ prefix)
        name_prefixes = [f"fuzzforge-module-{module_identifier}", module_identifier]

        for prefix in name_prefixes:
            for tag in tags_to_check:
                image_name = f"localhost/{prefix}:{tag}"
                if engine.image_exists(image_name):
                    return True

        return False

    def _get_local_image_name(self, module_identifier: str) -> str:
        """Get the full local image name for a module.

        :param module_identifier: Name/identifier of the module.
        :returns: Full image name (may or may not have localhost prefix).

        """
        engine = self._get_engine()

        # Try common tags
        tags_to_check = ["latest", "0.1.0", "0.0.1"]

        # Check OSS local builds first (no localhost/ prefix)
        for tag in tags_to_check:
            # Direct module name (fuzzforge-cargo-fuzzer:0.1.0)
            direct_name = f"{module_identifier}:{tag}"
            if engine.image_exists(direct_name):
                return direct_name

            # With fuzzforge- prefix if not already present
            if not module_identifier.startswith("fuzzforge-"):
                prefixed_name = f"fuzzforge-{module_identifier}:{tag}"
                if engine.image_exists(prefixed_name):
                    return prefixed_name

        # Check registry-style naming (localhost/ prefix)
        for tag in tags_to_check:
            # Standard convention: localhost/fuzzforge-module-{name}:{tag}
            prefixed_name = f"localhost/fuzzforge-module-{module_identifier}:{tag}"
            if engine.image_exists(prefixed_name):
                return prefixed_name

            # Legacy short form: localhost/{name}:{tag}
            short_name = f"localhost/{module_identifier}:{tag}"
            if engine.image_exists(short_name):
                return short_name

        # Default fallback
        return f"localhost/{module_identifier}:latest"

    def _pull_module_image(self, module_identifier: str, registry_url: str, tag: str = "latest") -> None:
        """Pull a module image from the container registry.

        :param module_identifier: Name/identifier of the module to pull.
        :param registry_url: Container registry URL.
        :param tag: Image tag to pull.
        :raises SandboxError: If pull fails.

        """
        logger = get_logger()
        engine = self._get_engine()

        # Construct full image name
        remote_image = f"{registry_url}/fuzzforge-module-{module_identifier}:{tag}"
        local_image = f"localhost/{module_identifier}:{tag}"

        logger.info("pulling module image from registry", module=module_identifier, remote_image=remote_image)

        try:
            # Pull the image using engine abstraction
            engine.pull_image(remote_image, timeout=300)

            logger.info("module image pulled successfully", module=module_identifier)

            # Tag the image locally for consistency
            engine.tag_image(remote_image, local_image)

            logger.debug("tagged image locally", local_image=local_image)

        except TimeoutError as exc:
            message = f"Module image pull timed out after 5 minutes: {module_identifier}"
            raise SandboxError(message) from exc
        except Exception as exc:
            message = (
                f"Failed to pull module image '{module_identifier}': {exc}\n"
                f"Registry: {registry_url}\n"
                f"Image: {remote_image}"
            )
            raise SandboxError(message) from exc

    def _ensure_module_image(self, module_identifier: str, registry_url: str = "", tag: str = "latest") -> None:
        """Ensure module image exists, pulling it if necessary.

        :param module_identifier: Name/identifier of the module image.
        :param registry_url: Container registry URL to pull from (empty = local-only mode).
        :param tag: Image tag to pull.
        :raises SandboxError: If image not found locally and no registry configured.

        """
        logger = get_logger()

        if self._check_image_exists(module_identifier):
            logger.debug("module image exists locally", module=module_identifier)
            return

        # If no registry configured, we're in local-only mode
        if not registry_url:
            raise SandboxError(
                f"Module image '{module_identifier}' not found locally.\n"
                "Build it with: make build-modules\n"
                "\n"
                "Or configure a registry URL via FUZZFORGE_REGISTRY__URL environment variable."
            )

        logger.info(
            "module image not found locally, pulling from registry",
            module=module_identifier,
            registry=registry_url,
            info="This may take a moment on first run",
        )
        self._pull_module_image(module_identifier, registry_url, tag)

        # Verify image now exists
        if not self._check_image_exists(module_identifier):
            message = (
                f"Module image '{module_identifier}' still not found after pull attempt.\n"
                f"Tried to pull from: {registry_url}/fuzzforge-module-{module_identifier}:{tag}"
            )
            raise SandboxError(message)

    def spawn_sandbox(self, module_identifier: str, input_volume: Path | None = None) -> str:
        """Create and prepare a sandbox container for module execution.

        Automatically pulls the module image from registry if it doesn't exist locally.

        :param module_identifier: Name/identifier of the module image.
        :param input_volume: Optional path to mount as /data/input in the container.
        :returns: The sandbox container identifier.
        :raises SandboxError: If sandbox creation fails.

        """
        logger = get_logger()
        engine = self._get_engine()

        # Ensure module image exists (auto-pull if needed)
        # Use registry settings from configuration
        registry_url = self._settings.registry.url
        tag = self._settings.registry.default_tag
        self._ensure_module_image(module_identifier, registry_url, tag)

        logger.info("spawning sandbox", module=module_identifier)
        try:
            image = self._get_local_image_name(module_identifier)

            # Build volume mappings
            volumes: dict[str, str] | None = None
            if input_volume:
                volumes = {str(input_volume): SANDBOX_INPUT_DIRECTORY}

            sandbox_id = engine.create_container(image=image, volumes=volumes)
            logger.info("sandbox spawned", sandbox=sandbox_id, module=module_identifier)
            return sandbox_id

        except TimeoutError as exc:
            message = f"Container creation timed out for module {module_identifier}"
            raise SandboxError(message) from exc
        except Exception as exc:
            message = f"Failed to spawn sandbox for module {module_identifier}"
            raise SandboxError(message) from exc

    def prepare_input_directory(
        self,
        assets_path: Path,
        configuration: dict[str, Any] | None = None,
    ) -> Path:
        """Prepare input directory with assets and configuration.

        Creates a temporary directory with input.json describing all resources.
        This directory can be volume-mounted into the container.

        :param assets_path: Path to the assets (file or directory).
        :param configuration: Optional module configuration dict.
        :returns: Path to prepared input directory.
        :raises SandboxError: If preparation fails.

        """
        logger = get_logger()

        logger.info("preparing input directory", assets=str(assets_path))

        try:
            # Create temporary directory - caller must clean it up after container finishes
            from tempfile import mkdtemp

            temp_path = Path(mkdtemp(prefix="fuzzforge-input-"))

            # Copy assets to temp directory
            if assets_path.exists():
                if assets_path.is_file():
                    # Check if it's a tar.gz archive that needs extraction
                    if assets_path.suffix == ".gz" or assets_path.name.endswith(".tar.gz"):
                        # Extract archive contents
                        import tarfile

                        with tarfile.open(assets_path, "r:gz") as tar:
                            tar.extractall(path=temp_path)
                        logger.debug("extracted tar.gz archive", archive=str(assets_path))
                    else:
                        # Single file - copy it
                        import shutil

                        shutil.copy2(assets_path, temp_path / assets_path.name)
                else:
                    # Directory - copy all files (including subdirectories)
                    import shutil

                    for item in assets_path.iterdir():
                        if item.is_file():
                            shutil.copy2(item, temp_path / item.name)
                        elif item.is_dir():
                            shutil.copytree(item, temp_path / item.name)

            # Scan files and directories and build resource list
            resources = []
            for item in temp_path.iterdir():
                if item.name == "input.json":
                    continue
                if item.is_file():
                    resources.append(
                        {
                            "name": item.stem,
                            "description": f"Input file: {item.name}",
                            "kind": "unknown",
                            "path": f"/data/input/{item.name}",
                        }
                    )
                elif item.is_dir():
                    resources.append(
                        {
                            "name": item.name,
                            "description": f"Input directory: {item.name}",
                            "kind": "unknown",
                            "path": f"/data/input/{item.name}",
                        }
                    )

            # Create input.json with settings and resources
            input_data = {
                "settings": configuration or {},
                "resources": resources,
            }
            input_json_path = temp_path / "input.json"
            input_json_path.write_text(json.dumps(input_data, indent=2))

            logger.debug("prepared input directory", resources=len(resources), path=str(temp_path))
            return temp_path

        except Exception as exc:
            message = f"Failed to prepare input directory"
            raise SandboxError(message) from exc

    def _push_config_to_sandbox(self, sandbox: str, configuration: dict[str, Any]) -> None:
        """Write module configuration to sandbox as config.json.

        :param sandbox: The sandbox container identifier.
        :param configuration: Configuration dictionary to write.

        """
        logger = get_logger()
        engine = self._get_engine()

        logger.info("writing configuration to sandbox", sandbox=sandbox)

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as config_file:
            config_path = Path(config_file.name)
            config_file.write(json.dumps(configuration, indent=2))

        try:
            engine.copy_to_container(sandbox, config_path, SANDBOX_INPUT_DIRECTORY)
        except Exception as exc:
            message = f"Failed to copy config.json: {exc}"
            raise SandboxError(message) from exc
        finally:
            config_path.unlink()

    def run_module(self, sandbox: str) -> None:
        """Start the sandbox and execute the module.

        :param sandbox: The sandbox container identifier.
        :raises ModuleExecutionError: If module execution fails.

        """
        logger = get_logger()
        engine = self._get_engine()

        logger.info("starting sandbox and running module", sandbox=sandbox)
        try:
            # The container runs its ENTRYPOINT (uv run module) when started
            exit_code, stdout, stderr = engine.start_container_attached(sandbox, timeout=600)

            if exit_code != 0:
                logger.error("module execution failed", sandbox=sandbox, stderr=stderr)
                message = f"Module execution failed: {stderr}"
                raise ModuleExecutionError(message)
            logger.info("module execution completed", sandbox=sandbox)

        except TimeoutError as exc:
            message = f"Module execution timed out after 10 minutes in sandbox {sandbox}"
            raise ModuleExecutionError(message) from exc
        except ModuleExecutionError:
            raise
        except Exception as exc:
            message = f"Module execution failed in sandbox {sandbox}"
            raise ModuleExecutionError(message) from exc

    def pull_results_from_sandbox(self, sandbox: str) -> Path:
        """Pull the results archive from the sandbox.

        :param sandbox: The sandbox container identifier.
        :returns: Path to the downloaded results archive (tar.gz file).
        :raises SandboxError: If pull operation fails.

        """
        logger = get_logger()
        engine = self._get_engine()

        logger.info("pulling results from sandbox", sandbox=sandbox)
        try:
            # Create temporary directory for results
            from tempfile import mkdtemp

            temp_dir = Path(mkdtemp(prefix="fuzzforge-results-"))

            # Copy entire output directory from container
            try:
                engine.copy_from_container(sandbox, SANDBOX_OUTPUT_DIRECTORY, temp_dir)
            except Exception:
                # If output directory doesn't exist, that's okay - module may not have produced results
                logger.warning("no results found in sandbox", sandbox=sandbox)

            # Create tar archive from results directory
            import tarfile

            archive_file = NamedTemporaryFile(delete=False, suffix=".tar.gz")
            archive_path = Path(archive_file.name)
            archive_file.close()

            with tarfile.open(archive_path, "w:gz") as tar:
                # The output is extracted into a subdirectory named after the source
                output_subdir = temp_dir / "output"
                if output_subdir.exists():
                    for item in output_subdir.iterdir():
                        tar.add(item, arcname=item.name)
                else:
                    for item in temp_dir.iterdir():
                        tar.add(item, arcname=item.name)

            # Clean up temp directory
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info("results pulled successfully", sandbox=sandbox, archive=str(archive_path))
            return archive_path

        except TimeoutError as exc:
            message = f"Timeout pulling results from sandbox {sandbox}"
            raise SandboxError(message) from exc
        except Exception as exc:
            message = f"Failed to pull results from sandbox {sandbox}"
            raise SandboxError(message) from exc

    def terminate_sandbox(self, sandbox: str) -> None:
        """Terminate and cleanup the sandbox container.

        :param sandbox: The sandbox container identifier.

        """
        logger = get_logger()
        engine = self._get_engine()

        logger.info("terminating sandbox", sandbox=sandbox)
        try:
            engine.remove_container(sandbox, force=True)
            logger.info("sandbox terminated", sandbox=sandbox)
        except Exception as exc:
            # Log but don't raise - cleanup should be best-effort
            logger.warning("failed to terminate sandbox", sandbox=sandbox, error=str(exc))

    async def execute(
        self,
        module_identifier: str,
        assets_path: Path,
        configuration: dict[str, Any] | None = None,
    ) -> Path:
        """Execute a module end-to-end.

        This is the main entry point that handles the complete execution flow:
        1. Spawn sandbox
        2. Push assets and configuration
        3. Run module
        4. Pull results
        5. Terminate sandbox

        :param module_identifier: Name/identifier of the module to execute.
        :param assets_path: Path to the input assets archive.
        :param configuration: Optional module configuration.
        :returns: Path to the results archive.
        :raises ModuleExecutionError: If any step fails.

        """
        logger = get_logger()
        sandbox: str | None = None
        input_dir: Path | None = None

        try:
            # 1. Prepare input directory with assets
            input_dir = self.prepare_input_directory(assets_path, configuration)

            # 2. Spawn sandbox with volume mount
            sandbox = self.spawn_sandbox(module_identifier, input_volume=input_dir)

            # 3. Run module
            self.run_module(sandbox)

            # 4. Pull results
            results_path = self.pull_results_from_sandbox(sandbox)

            logger.info(
                "module execution completed successfully",
                module=module_identifier,
                results=str(results_path),
            )

            return results_path

        finally:
            # 5. Always cleanup
            if sandbox:
                self.terminate_sandbox(sandbox)
            if input_dir and input_dir.exists():
                import shutil

                shutil.rmtree(input_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Continuous/Background Execution Methods
    # -------------------------------------------------------------------------

    def start_module_continuous(
        self,
        module_identifier: str,
        assets_path: Path,
        configuration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a module in continuous/background mode without waiting.

        Returns immediately with container info. Use read_module_output() to
        get current status and stop_module_continuous() to stop.

        :param module_identifier: Name/identifier of the module to execute.
        :param assets_path: Path to the input assets archive.
        :param configuration: Optional module configuration.
        :returns: Dict with container_id, input_dir for later cleanup.

        """
        logger = get_logger()

        # 1. Prepare input directory with assets
        input_dir = self.prepare_input_directory(assets_path, configuration)

        # 2. Spawn sandbox with volume mount
        sandbox = self.spawn_sandbox(module_identifier, input_volume=input_dir)

        # 3. Start container (non-blocking)
        engine = self._get_engine()
        engine.start_container(sandbox)

        logger.info(
            "module started in continuous mode",
            module=module_identifier,
            container_id=sandbox,
        )

        return {
            "container_id": sandbox,
            "input_dir": str(input_dir),
            "module": module_identifier,
        }

    def read_module_output(self, container_id: str, output_file: str = "/data/output/stream.jsonl") -> str:
        """Read output file from a running module container.

        :param container_id: The container identifier.
        :param output_file: Path to output file inside container.
        :returns: File contents as string.

        """
        engine = self._get_engine()
        return engine.read_file_from_container(container_id, output_file)

    def get_module_status(self, container_id: str) -> str:
        """Get the status of a running module container.

        :param container_id: The container identifier.
        :returns: Container status (e.g., "running", "exited").

        """
        engine = self._get_engine()
        return engine.get_container_status(container_id)

    def stop_module_continuous(self, container_id: str, input_dir: str | None = None) -> Path:
        """Stop a continuously running module and collect results.

        :param container_id: The container identifier.
        :param input_dir: Optional input directory to cleanup.
        :returns: Path to the results archive.

        """
        logger = get_logger()
        engine = self._get_engine()

        try:
            # 1. Stop the container gracefully
            status = engine.get_container_status(container_id)
            if status == "running":
                engine.stop_container(container_id, timeout=10)
                logger.info("stopped running container", container_id=container_id)

            # 2. Pull results
            results_path = self.pull_results_from_sandbox(container_id)

            logger.info("collected results from continuous session", results=str(results_path))

            return results_path

        finally:
            # 3. Cleanup
            self.terminate_sandbox(container_id)
            if input_dir:
                import shutil

                shutil.rmtree(input_dir, ignore_errors=True)
