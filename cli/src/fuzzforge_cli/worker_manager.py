"""
Worker lifecycle management for FuzzForge CLI.

Manages on-demand startup and shutdown of Temporal workers using Docker Compose.
"""
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

import logging
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

import requests
import yaml
from rich.console import Console
from rich.status import Status

logger = logging.getLogger(__name__)
console = Console()


class WorkerManager:
    """
    Manages Temporal worker lifecycle using docker-compose.

    This class handles:
    - Checking if workers are running
    - Starting workers on demand
    - Waiting for workers to be ready
    - Stopping workers when done
    """

    def __init__(
        self,
        compose_file: Optional[Path] = None,
        startup_timeout: int = 60,
        health_check_interval: float = 2.0
    ):
        """
        Initialize WorkerManager.

        Args:
            compose_file: Path to docker-compose.yml (defaults to auto-detect)
            startup_timeout: Maximum seconds to wait for worker startup
            health_check_interval: Seconds between health checks
        """
        self.compose_file = compose_file or self._find_compose_file()
        self.startup_timeout = startup_timeout
        self.health_check_interval = health_check_interval

    def _find_compose_file(self) -> Path:
        """
        Auto-detect docker-compose.yml location using multiple strategies.

        Strategies (in order):
        1. Query backend API for host path
        2. Search upward for .fuzzforge marker directory
        3. Use FUZZFORGE_ROOT environment variable
        4. Fallback to current directory

        Returns:
            Path to docker-compose.yml

        Raises:
            FileNotFoundError: If docker-compose.yml cannot be located
        """
        # Strategy 1: Ask backend for location
        try:
            backend_url = os.getenv("FUZZFORGE_API_URL", "http://localhost:8000")
            response = requests.get(f"{backend_url}/system/info", timeout=2)
            if response.ok:
                info = response.json()
                if compose_path_str := info.get("docker_compose_path"):
                    compose_path = Path(compose_path_str)
                    if compose_path.exists():
                        logger.debug(f"Found docker-compose.yml via backend API: {compose_path}")
                        return compose_path
        except Exception as e:
            logger.debug(f"Backend API not reachable for path lookup: {e}")

        # Strategy 2: Search upward for .fuzzforge marker directory
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / ".fuzzforge").exists():
                compose_path = parent / "docker-compose.yml"
                if compose_path.exists():
                    logger.debug(f"Found docker-compose.yml via .fuzzforge marker: {compose_path}")
                    return compose_path

        # Strategy 3: Environment variable
        if fuzzforge_root := os.getenv("FUZZFORGE_ROOT"):
            compose_path = Path(fuzzforge_root) / "docker-compose.yml"
            if compose_path.exists():
                logger.debug(f"Found docker-compose.yml via FUZZFORGE_ROOT: {compose_path}")
                return compose_path

        # Strategy 4: Fallback to current directory
        compose_path = Path("docker-compose.yml")
        if compose_path.exists():
            return compose_path

        raise FileNotFoundError(
            "Cannot find docker-compose.yml. Ensure backend is running, "
            "run from FuzzForge directory, or set FUZZFORGE_ROOT environment variable."
        )

    def _get_workers_dir(self) -> Path:
        """
        Get the workers directory path.

        Uses same strategy as _find_compose_file():
        1. Query backend API
        2. Derive from compose_file location
        3. Use FUZZFORGE_ROOT

        Returns:
            Path to workers directory
        """
        # Strategy 1: Ask backend
        try:
            backend_url = os.getenv("FUZZFORGE_API_URL", "http://localhost:8000")
            response = requests.get(f"{backend_url}/system/info", timeout=2)
            if response.ok:
                info = response.json()
                if workers_dir_str := info.get("workers_dir"):
                    workers_dir = Path(workers_dir_str)
                    if workers_dir.exists():
                        return workers_dir
        except Exception:
            pass

        # Strategy 2: Derive from compose file location
        if self.compose_file.exists():
            workers_dir = self.compose_file.parent / "workers"
            if workers_dir.exists():
                return workers_dir

        # Strategy 3: Use environment variable
        if fuzzforge_root := os.getenv("FUZZFORGE_ROOT"):
            workers_dir = Path(fuzzforge_root) / "workers"
            if workers_dir.exists():
                return workers_dir

        # Fallback
        return Path("workers")

    def _detect_platform(self) -> str:
        """
        Detect the current platform.

        Returns:
            Platform string: "linux/amd64" or "linux/arm64"
        """
        machine = platform.machine().lower()
        system = platform.system().lower()

        logger.debug(f"Platform detection: machine={machine}, system={system}")

        # Normalize machine architecture
        if machine in ["x86_64", "amd64", "x64"]:
            detected = "linux/amd64"
        elif machine in ["arm64", "aarch64", "armv8", "arm64v8"]:
            detected = "linux/arm64"
        else:
            # Fallback to amd64 for unknown architectures
            logger.warning(
                f"Unknown architecture '{machine}' detected, falling back to linux/amd64. "
                f"Please report this issue if you're experiencing problems."
            )
            detected = "linux/amd64"

        logger.info(f"Detected platform: {detected}")
        return detected

    def _read_worker_metadata(self, vertical: str) -> dict:
        """
        Read worker metadata.yaml for a vertical.

        Args:
            vertical: Worker vertical name (e.g., "android", "python")

        Returns:
            Dictionary containing metadata, or empty dict if not found
        """
        try:
            workers_dir = self._get_workers_dir()
            metadata_file = workers_dir / vertical / "metadata.yaml"

            if not metadata_file.exists():
                logger.debug(f"No metadata.yaml found for {vertical}")
                return {}

            with open(metadata_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.debug(f"Failed to read metadata for {vertical}: {e}")
            return {}

    def _select_dockerfile(self, vertical: str) -> str:
        """
        Select the appropriate Dockerfile for the current platform.

        Args:
            vertical: Worker vertical name

        Returns:
            Dockerfile name (e.g., "Dockerfile.amd64", "Dockerfile.arm64")
        """
        detected_platform = self._detect_platform()
        metadata = self._read_worker_metadata(vertical)

        if not metadata:
            # No metadata: use default Dockerfile
            logger.debug(f"No metadata for {vertical}, using Dockerfile")
            return "Dockerfile"

        platforms = metadata.get("platforms", {})

        if not platforms:
            # Metadata exists but no platform definitions
            logger.debug(f"No platform definitions in metadata for {vertical}, using Dockerfile")
            return "Dockerfile"

        # Try detected platform first
        if detected_platform in platforms:
            dockerfile = platforms[detected_platform].get("dockerfile", "Dockerfile")
            logger.info(f"✓ Selected {dockerfile} for {vertical} on {detected_platform}")
            return dockerfile

        # Fallback to default platform
        default_platform = metadata.get("default_platform", "linux/amd64")
        logger.warning(
            f"Platform {detected_platform} not found in metadata for {vertical}, "
            f"falling back to default: {default_platform}"
        )

        if default_platform in platforms:
            dockerfile = platforms[default_platform].get("dockerfile", "Dockerfile.amd64")
            logger.info(f"Using default platform {default_platform}: {dockerfile}")
            return dockerfile

        # Last resort: just use Dockerfile
        logger.warning(f"No suitable Dockerfile found for {vertical}, using 'Dockerfile'")
        return "Dockerfile"

    def _run_docker_compose(self, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        """
        Run docker compose command with optional environment variables.

        Args:
            *args: Arguments to pass to docker compose
            env: Optional environment variables to set

        Returns:
            CompletedProcess with result

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        cmd = ["docker", "compose", "-f", str(self.compose_file)] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")

        # Merge with current environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
            logger.debug(f"Environment overrides: {env}")

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env=full_env
        )

    def _service_to_container_name(self, service_name: str) -> str:
        """
        Convert service name to container name based on docker-compose naming convention.

        Args:
            service_name: Docker Compose service name (e.g., "worker-python")

        Returns:
            Container name (e.g., "fuzzforge-worker-python")
        """
        return f"fuzzforge-{service_name}"

    def is_worker_running(self, service_name: str) -> bool:
        """
        Check if a worker service is running.

        Args:
            service_name: Name of the Docker Compose service (e.g., "worker-ossfuzz")

        Returns:
            True if container is running, False otherwise
        """
        try:
            container_name = self._service_to_container_name(service_name)
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                capture_output=True,
                text=True,
                check=False
            )

            # Output is "true" or "false"
            return result.stdout.strip().lower() == "true"

        except Exception as e:
            logger.debug(f"Failed to check worker status: {e}")
            return False

    def start_worker(self, service_name: str) -> bool:
        """
        Start a worker service using docker-compose with platform-specific Dockerfile.

        Args:
            service_name: Name of the Docker Compose service to start (e.g., "worker-android")

        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Extract vertical name from service name
            vertical = service_name.replace("worker-", "")

            # Detect platform and select appropriate Dockerfile
            detected_platform = self._detect_platform()
            dockerfile = self._select_dockerfile(vertical)

            # Set environment variable for docker-compose
            env_var_name = f"{vertical.upper()}_DOCKERFILE"
            env = {env_var_name: dockerfile}

            console.print(
                f"🚀 Starting worker: {service_name} "
                f"(platform: {detected_platform}, using {dockerfile})"
            )

            # Use docker-compose up with --build to ensure correct Dockerfile is used
            result = self._run_docker_compose("up", "-d", "--build", service_name, env=env)

            logger.info(f"Worker {service_name} started with {dockerfile}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start worker {service_name}: {e.stderr}")
            console.print(f"❌ Failed to start worker: {e.stderr}", style="red")
            console.print(f"💡 Start the worker manually: docker compose up -d {service_name}", style="yellow")
            return False

        except Exception as e:
            logger.error(f"Unexpected error starting worker {service_name}: {e}")
            console.print(f"❌ Unexpected error: {e}", style="red")
            return False

    def _get_container_state(self, service_name: str) -> str:
        """
        Get the current state of a container (running, created, restarting, etc.).

        Args:
            service_name: Name of the Docker Compose service

        Returns:
            Container state string (running, created, restarting, exited, etc.) or "unknown"
        """
        try:
            container_name = self._service_to_container_name(service_name)
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "unknown"
        except Exception as e:
            logger.debug(f"Failed to get container state: {e}")
            return "unknown"

    def _get_health_status(self, container_name: str) -> str:
        """
        Get container health status.

        Args:
            container_name: Docker container name

        Returns:
            Health status: "healthy", "unhealthy", "starting", "none", or "unknown"
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_name],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                return "unknown"

            health_status = result.stdout.strip()

            if health_status == "<no value>" or health_status == "":
                return "none"  # No health check defined

            return health_status  # healthy, unhealthy, starting

        except Exception as e:
            logger.debug(f"Failed to check health: {e}")
            return "unknown"

    def wait_for_worker_ready(self, service_name: str, timeout: Optional[int] = None) -> bool:
        """
        Wait for a worker to be healthy and ready to process tasks.
        Shows live progress updates during startup.

        Args:
            service_name: Name of the Docker Compose service
            timeout: Maximum seconds to wait (uses instance default if not specified)

        Returns:
            True if worker is ready, False if timeout reached
        """
        timeout = timeout or self.startup_timeout
        start_time = time.time()
        container_name = self._service_to_container_name(service_name)
        last_status_msg = ""

        with Status("[bold cyan]Starting worker...", console=console, spinner="dots") as status:
            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)

                # Get container state
                container_state = self._get_container_state(service_name)

                # Get health status
                health_status = self._get_health_status(container_name)

                # Build status message based on current state
                if container_state == "created":
                    status_msg = f"[cyan]Worker starting... ({elapsed}s)[/cyan]"
                elif container_state == "restarting":
                    status_msg = f"[yellow]Worker restarting... ({elapsed}s)[/yellow]"
                elif container_state == "running":
                    if health_status == "starting":
                        status_msg = f"[cyan]Worker running, health check starting... ({elapsed}s)[/cyan]"
                    elif health_status == "unhealthy":
                        status_msg = f"[yellow]Worker running, health check: unhealthy ({elapsed}s)[/yellow]"
                    elif health_status == "healthy":
                        status_msg = f"[green]Worker healthy! ({elapsed}s)[/green]"
                        status.update(status_msg)
                        console.print(f"✅ Worker ready: {service_name} (took {elapsed}s)")
                        logger.info(f"Worker {service_name} is healthy (took {elapsed}s)")
                        return True
                    elif health_status == "none":
                        # No health check defined, assume ready
                        status_msg = f"[green]Worker running (no health check) ({elapsed}s)[/green]"
                        status.update(status_msg)
                        console.print(f"✅ Worker ready: {service_name} (took {elapsed}s)")
                        logger.info(f"Worker {service_name} is running, no health check (took {elapsed}s)")
                        return True
                    else:
                        status_msg = f"[cyan]Worker running ({elapsed}s)[/cyan]"
                elif not container_state or container_state == "exited":
                    status_msg = f"[yellow]Waiting for container to start... ({elapsed}s)[/yellow]"
                else:
                    status_msg = f"[cyan]Worker state: {container_state} ({elapsed}s)[/cyan]"

                # Show helpful hints at certain intervals
                if elapsed == 10:
                    status_msg += " [dim](pulling image if not cached)[/dim]"
                elif elapsed == 30:
                    status_msg += " [dim](large images can take time)[/dim]"
                elif elapsed == 60:
                    status_msg += " [dim](still working...)[/dim]"

                # Update status if changed
                if status_msg != last_status_msg:
                    status.update(status_msg)
                    last_status_msg = status_msg
                    logger.debug(f"Worker {service_name} - state: {container_state}, health: {health_status}")

                time.sleep(self.health_check_interval)

            # Timeout reached
            elapsed = int(time.time() - start_time)
            logger.warning(f"Worker {service_name} did not become ready within {elapsed}s")
            console.print(f"⚠️  Worker startup timeout after {elapsed}s", style="yellow")
            console.print(f"   Last state: {container_state}, health: {health_status}", style="dim")
            return False

    def stop_worker(self, service_name: str) -> bool:
        """
        Stop a worker service using docker-compose.

        Args:
            service_name: Name of the Docker Compose service to stop

        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            console.print(f"🛑 Stopping worker: {service_name}")

            # Use docker-compose down to stop and remove the service
            result = self._run_docker_compose("stop", service_name)

            logger.info(f"Worker {service_name} stopped")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop worker {service_name}: {e.stderr}")
            console.print(f"❌ Failed to stop worker: {e.stderr}", style="red")
            return False

        except Exception as e:
            logger.error(f"Unexpected error stopping worker {service_name}: {e}")
            console.print(f"❌ Unexpected error: {e}", style="red")
            return False

    def stop_all_workers(self) -> bool:
        """
        Stop all running FuzzForge worker containers.

        This uses `docker stop` to stop worker containers individually,
        avoiding the Docker Compose profile issue and preventing accidental
        shutdown of core services.

        Returns:
            True if all workers stopped successfully, False otherwise
        """
        try:
            console.print("🛑 Stopping all FuzzForge workers...")

            # Get list of all running worker containers
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=fuzzforge-worker-", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=False
            )

            running_workers = [name.strip() for name in result.stdout.splitlines() if name.strip()]

            if not running_workers:
                console.print("✓ No workers running")
                return True

            console.print(f"Found {len(running_workers)} running worker(s):")
            for worker in running_workers:
                console.print(f"  - {worker}")

            # Stop each worker container individually using docker stop
            # This is safer than docker compose down and won't affect core services
            failed_workers = []
            for worker in running_workers:
                try:
                    logger.info(f"Stopping {worker}...")
                    result = subprocess.run(
                        ["docker", "stop", worker],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=30
                    )
                    console.print(f"  ✓ Stopped {worker}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to stop {worker}: {e.stderr}")
                    failed_workers.append(worker)
                    console.print(f"  ✗ Failed to stop {worker}", style="red")
                except subprocess.TimeoutExpired:
                    logger.error(f"Timeout stopping {worker}")
                    failed_workers.append(worker)
                    console.print(f"  ✗ Timeout stopping {worker}", style="red")

            if failed_workers:
                console.print(f"\n⚠️  {len(failed_workers)} worker(s) failed to stop", style="yellow")
                console.print("💡 Try manually: docker stop " + " ".join(failed_workers), style="dim")
                return False

            console.print("\n✅ All workers stopped")
            logger.info("All workers stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Unexpected error stopping workers: {e}")
            console.print(f"❌ Unexpected error: {e}", style="red")
            return False

    def ensure_worker_running(
        self,
        worker_info: Dict[str, Any],
        auto_start: bool = True
    ) -> bool:
        """
        Ensure a worker is running, starting it if necessary.

        Args:
            worker_info: Worker information dict from API (contains worker_service, etc.)
            auto_start: Whether to automatically start the worker if not running

        Returns:
            True if worker is running, False otherwise
        """
        # Get worker_service (docker-compose service name)
        service_name = worker_info.get("worker_service", f"worker-{worker_info['vertical']}")
        vertical = worker_info["vertical"]

        # Check if already running
        if self.is_worker_running(service_name):
            console.print(f"✓ Worker already running: {vertical}")
            return True

        if not auto_start:
            console.print(
                f"⚠️  Worker not running: {vertical}. Use --auto-start to start automatically.",
                style="yellow"
            )
            return False

        # Start the worker
        if not self.start_worker(service_name):
            return False

        # Wait for it to be ready
        return self.wait_for_worker_ready(service_name)
