"""
Atheris Fuzzer Module

Reusable module for fuzzing Python code using Atheris.
Discovers and fuzzes user-provided Python targets with TestOneInput() function.
"""

import asyncio
import base64
import importlib.util
import logging
import multiprocessing
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import uuid

import httpx
from modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding

logger = logging.getLogger(__name__)


def _run_atheris_in_subprocess(
    target_path_str: str,
    corpus_dir_str: str,
    max_iterations: int,
    timeout_seconds: int,
    shared_crashes: Any,
    exec_counter: multiprocessing.Value,
    crash_counter: multiprocessing.Value,
    coverage_counter: multiprocessing.Value
):
    """
    Run atheris.Fuzz() in a separate process to isolate os._exit() calls.

    This function runs in a subprocess and loads the target module,
    sets up atheris, and runs fuzzing. Stats are communicated via shared memory.

    Args:
        target_path_str: String path to target file
        corpus_dir_str: String path to corpus directory
        max_iterations: Maximum fuzzing iterations
        timeout_seconds: Timeout in seconds
        shared_crashes: Manager().list() for storing crash details
        exec_counter: Shared counter for executions
        crash_counter: Shared counter for crashes
        coverage_counter: Shared counter for coverage edges
    """
    import atheris
    import importlib.util
    import traceback
    from pathlib import Path

    target_path = Path(target_path_str)
    total_executions = 0

    # NOTE: Crash details are written directly to shared_crashes (Manager().list())
    # so they can be accessed by parent process after subprocess exits.
    # We don't use a local crashes list because os._exit() prevents cleanup code.

    try:
        # Load target module in subprocess
        module_name = f"fuzz_target_{uuid.uuid4().hex[:8]}"
        spec = importlib.util.spec_from_file_location(module_name, target_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {target_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "TestOneInput"):
            raise AttributeError("Module does not have TestOneInput() function")

        test_one_input = module.TestOneInput

        # Wrapper to track executions and crashes
        def fuzz_wrapper(data):
            nonlocal total_executions
            total_executions += 1

            # Update shared counter for live stats
            with exec_counter.get_lock():
                exec_counter.value += 1

            try:
                test_one_input(data)
            except Exception as e:
                # Capture crash details to shared memory
                crash_info = {
                    "input": bytes(data),  # Convert to bytes for serialization
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                    "stack_trace": traceback.format_exc(),
                    "execution": total_executions
                }
                # Write to shared memory so parent process can access crash details
                shared_crashes.append(crash_info)

                # Update shared crash counter
                with crash_counter.get_lock():
                    crash_counter.value += 1

                # Re-raise so Atheris detects it
                raise

        # Check for dictionary file in target directory
        dict_args = []
        target_dir = target_path.parent
        for dict_name in ["fuzz.dict", "fuzzing.dict", "dict.txt"]:
            dict_path = target_dir / dict_name
            if dict_path.exists():
                dict_args.append(f"-dict={dict_path}")
                break

        # Configure Atheris
        atheris_args = [
            "atheris_fuzzer",
            f"-runs={max_iterations}",
            f"-max_total_time={timeout_seconds}",
            "-print_final_stats=1"
        ] + dict_args + [corpus_dir_str]  # Corpus directory as positional arg

        atheris.Setup(atheris_args, fuzz_wrapper)

        # Run fuzzing (this will call os._exit() when done)
        atheris.Fuzz()

    except SystemExit:
        # Atheris exits when done - this is normal
        # Crash details already written to shared_crashes
        pass
    except Exception:
        # Fatal error - traceback already written to shared memory
        # via crash handler in fuzz_wrapper
        pass


class AtherisFuzzer(BaseModule):
    """
    Atheris fuzzing module - discovers and fuzzes Python code.

    This module can be used by any workflow to fuzz Python targets.
    """

    def __init__(self):
        super().__init__()
        self.crashes = []
        self.total_executions = 0
        self.start_time = None
        self.last_stats_time = 0
        self.run_id = None

    def get_metadata(self) -> ModuleMetadata:
        """Return module metadata"""
        return ModuleMetadata(
            name="atheris_fuzzer",
            version="1.0.0",
            description="Python fuzzing using Atheris - discovers and fuzzes TestOneInput() functions",
            author="FuzzForge Team",
            category="fuzzer",
            tags=["fuzzing", "atheris", "python", "coverage"],
            input_schema={
                "type": "object",
                "properties": {
                    "target_file": {
                        "type": "string",
                        "description": "Python file with TestOneInput() function (auto-discovered if not specified)"
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum fuzzing iterations",
                        "default": 100000
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Fuzzing timeout in seconds",
                        "default": 300
                    },
                    "stats_callback": {
                        "description": "Optional callback for real-time statistics"
                    }
                }
            },
            requires_workspace=True
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate fuzzing configuration"""
        max_iterations = config.get("max_iterations", 100000)
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(f"max_iterations must be positive integer, got: {max_iterations}")

        timeout = config.get("timeout_seconds", 300)
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError(f"timeout_seconds must be positive integer, got: {timeout}")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute Atheris fuzzing on user code.

        Args:
            config: Fuzzing configuration
            workspace: Path to user's uploaded code

        Returns:
            ModuleResult with crash findings
        """
        self.start_timer()
        self.start_time = time.time()

        # Validate configuration
        self.validate_config(config)
        self.validate_workspace(workspace)

        # Extract config
        target_file = config.get("target_file")
        max_iterations = config.get("max_iterations", 100000)
        timeout_seconds = config.get("timeout_seconds", 300)
        stats_callback = config.get("stats_callback")
        self.run_id = config.get("run_id")

        logger.info(
            f"Starting Atheris fuzzing (max_iterations={max_iterations}, "
            f"timeout={timeout_seconds}s, target={target_file or 'auto-discover'})"
        )

        try:
            # Step 1: Discover or load target
            target_path = self._discover_target(workspace, target_file)
            logger.info(f"Using fuzz target: {target_path}")

            # Step 2: Load target module
            test_one_input = self._load_target_module(target_path)
            logger.info(f"Loaded TestOneInput function from {target_path}")

            # Step 3: Run fuzzing
            await self._run_fuzzing(
                test_one_input=test_one_input,
                target_path=target_path,
                workspace=workspace,
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds,
                stats_callback=stats_callback
            )

            # Step 4: Generate findings from crashes
            findings = await self._generate_findings(target_path)

            logger.info(
                f"Fuzzing completed: {self.total_executions} executions, "
                f"{len(self.crashes)} crashes found"
            )

            # Generate SARIF report (always, even with no findings)
            from modules.reporter import SARIFReporter
            reporter = SARIFReporter()
            reporter_config = {
                "findings": findings,
                "tool_name": "Atheris Fuzzer",
                "tool_version": self._metadata.version
            }
            reporter_result = await reporter.execute(reporter_config, workspace)
            sarif_report = reporter_result.sarif

            return ModuleResult(
                module=self._metadata.name,
                version=self._metadata.version,
                status="success",
                execution_time=self.get_execution_time(),
                findings=findings,
                summary={
                    "total_executions": self.total_executions,
                    "crashes_found": len(self.crashes),
                    "execution_time": self.get_execution_time(),
                    "target_file": str(target_path.relative_to(workspace))
                },
                metadata={
                    "max_iterations": max_iterations,
                    "timeout_seconds": timeout_seconds
                },
                sarif=sarif_report
            )

        except Exception as e:
            logger.error(f"Fuzzing failed: {e}", exc_info=True)
            return self.create_result(
                findings=[],
                status="failed",
                error=str(e)
            )

    def _discover_target(self, workspace: Path, target_file: Optional[str]) -> Path:
        """
        Discover fuzz target in workspace.

        Args:
            workspace: Path to workspace
            target_file: Explicit target file or None for auto-discovery

        Returns:
            Path to target file
        """
        if target_file:
            # Use specified target
            target_path = workspace / target_file
            if not target_path.exists():
                raise FileNotFoundError(f"Target file not found: {target_file}")
            return target_path

        # Auto-discover: look for fuzz_*.py or *_fuzz.py
        logger.info("Auto-discovering fuzz targets...")

        candidates = []
        # Use rglob for recursive search (searches all subdirectories)
        for pattern in ["fuzz_*.py", "*_fuzz.py", "fuzz_target.py"]:
            matches = list(workspace.rglob(pattern))
            candidates.extend(matches)

        if not candidates:
            raise FileNotFoundError(
                "No fuzz targets found. Expected files matching: fuzz_*.py, *_fuzz.py, or fuzz_target.py"
            )

        # Use first candidate
        target = candidates[0]
        if len(candidates) > 1:
            logger.warning(
                f"Multiple fuzz targets found: {[str(c) for c in candidates]}. "
                f"Using: {target.name}"
            )

        return target

    def _load_target_module(self, target_path: Path) -> Callable:
        """
        Load target module and get TestOneInput function.

        Args:
            target_path: Path to Python file with TestOneInput

        Returns:
            TestOneInput function
        """
        # Add target directory to sys.path
        target_dir = target_path.parent
        if str(target_dir) not in sys.path:
            sys.path.insert(0, str(target_dir))

        # Load module dynamically
        module_name = target_path.stem
        spec = importlib.util.spec_from_file_location(module_name, target_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {target_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get TestOneInput function
        if not hasattr(module, "TestOneInput"):
            raise AttributeError(
                f"Module {module_name} does not have TestOneInput() function. "
                "Atheris requires a TestOneInput(data: bytes) function."
            )

        return module.TestOneInput

    async def _run_fuzzing(
        self,
        test_one_input: Callable,
        target_path: Path,
        workspace: Path,
        max_iterations: int,
        timeout_seconds: int,
        stats_callback: Optional[Callable] = None
    ):
        """
        Run Atheris fuzzing with real-time monitoring.

        Args:
            test_one_input: TestOneInput function to fuzz (not used, loaded in subprocess)
            target_path: Path to target file
            workspace: Path to workspace directory
            max_iterations: Max iterations
            timeout_seconds: Timeout in seconds
            stats_callback: Optional callback for stats
        """
        self.crashes = []
        self.total_executions = 0

        # Create corpus directory in workspace
        corpus_dir = workspace / ".fuzzforge_corpus"
        corpus_dir.mkdir(exist_ok=True)
        logger.info(f"Using corpus directory: {corpus_dir}")

        logger.info(f"Starting Atheris fuzzer in subprocess (max_runs={max_iterations}, timeout={timeout_seconds}s)...")

        # Create shared memory for subprocess communication
        ctx = multiprocessing.get_context('spawn')
        manager = ctx.Manager()
        shared_crashes = manager.list()  # Shared list for crash details
        exec_counter = ctx.Value('i', 0)  # Shared execution counter
        crash_counter = ctx.Value('i', 0)  # Shared crash counter
        coverage_counter = ctx.Value('i', 0)  # Shared coverage counter

        # Start fuzzing in subprocess
        process = ctx.Process(
            target=_run_atheris_in_subprocess,
            args=(str(target_path), str(corpus_dir), max_iterations, timeout_seconds, shared_crashes, exec_counter, crash_counter, coverage_counter)
        )

        # Run fuzzing in a separate task with monitoring
        async def monitor_stats():
            """Monitor and report stats every 0.5 seconds"""
            while True:
                await asyncio.sleep(0.5)

                if stats_callback:
                    elapsed = time.time() - self.start_time
                    # Read from shared counters
                    current_execs = exec_counter.value
                    current_crashes = crash_counter.value
                    current_coverage = coverage_counter.value
                    execs_per_sec = current_execs / elapsed if elapsed > 0 else 0

                    # Count corpus files
                    try:
                        corpus_size = len(list(corpus_dir.iterdir())) if corpus_dir.exists() else 0
                    except Exception:
                        corpus_size = 0

                    # TODO: Get real coverage from Atheris
                    # For now use corpus_size as proxy
                    coverage_value = current_coverage if current_coverage > 0 else corpus_size

                    await stats_callback({
                        "total_execs": current_execs,
                        "execs_per_sec": execs_per_sec,
                        "crashes": current_crashes,
                        "corpus_size": corpus_size,
                        "coverage": coverage_value,  # Using corpus as coverage proxy
                        "elapsed_time": int(elapsed)
                    })

        # Start monitoring task
        monitor_task = None
        if stats_callback:
            monitor_task = asyncio.create_task(monitor_stats())

        try:
            # Start subprocess
            process.start()
            logger.info(f"Fuzzing subprocess started (PID: {process.pid})")

            # Wait for subprocess to complete
            while process.is_alive():
                await asyncio.sleep(0.1)

            # NOTE: We cannot use result_queue because Atheris calls os._exit()
            # which terminates immediately without putting results in the queue.
            # Instead, we rely on shared memory (Manager().list() and Value counters).

            # Read final values from shared memory
            self.total_executions = exec_counter.value
            total_crashes = crash_counter.value

            # Read crash details from shared memory and convert to our format
            self.crashes = []
            for crash_data in shared_crashes:
                # Reconstruct crash info with exception object
                crash_info = {
                    "input": crash_data["input"],
                    "exception": Exception(crash_data["exception_message"]),
                    "exception_type": crash_data["exception_type"],
                    "stack_trace": crash_data["stack_trace"],
                    "execution": crash_data["execution"]
                }
                self.crashes.append(crash_info)

                logger.warning(
                    f"Crash found (execution {crash_data['execution']}): "
                    f"{crash_data['exception_type']}: {crash_data['exception_message']}"
                )

            logger.info(f"Fuzzing completed: {self.total_executions} executions, {total_crashes} crashes found")

            # Send final stats update
            if stats_callback:
                elapsed = time.time() - self.start_time
                execs_per_sec = self.total_executions / elapsed if elapsed > 0 else 0

                # Count final corpus size
                try:
                    final_corpus_size = len(list(corpus_dir.iterdir())) if corpus_dir.exists() else 0
                except Exception:
                    final_corpus_size = 0

                # TODO: Parse coverage from Atheris output
                # For now, use corpus size as proxy (corpus grows with coverage)
                # libFuzzer writes coverage to stdout but sys.stdout redirection
                # doesn't work because it writes to FD 1 directly from C++
                final_coverage = coverage_counter.value if coverage_counter.value > 0 else final_corpus_size

                await stats_callback({
                    "total_execs": self.total_executions,
                    "execs_per_sec": execs_per_sec,
                    "crashes": total_crashes,
                    "corpus_size": final_corpus_size,
                    "coverage": final_coverage,
                    "elapsed_time": int(elapsed)
                })

            # Wait for process to fully terminate
            process.join(timeout=5)

            if process.exitcode is not None and process.exitcode != 0:
                logger.warning(f"Subprocess exited with code: {process.exitcode}")

        except Exception as e:
            logger.error(f"Fuzzing execution error: {e}")
            if process.is_alive():
                logger.warning("Terminating fuzzing subprocess...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
            raise
        finally:
            # Stop monitoring
            if monitor_task:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

    async def _generate_findings(self, target_path: Path) -> List[ModuleFinding]:
        """
        Generate ModuleFinding objects from crashes.

        Args:
            target_path: Path to target file

        Returns:
            List of findings
        """
        findings = []

        for idx, crash in enumerate(self.crashes):
            # Encode crash input for storage
            crash_input_b64 = base64.b64encode(crash["input"]).decode()

            finding = self.create_finding(
                title=f"Crash: {crash['exception_type']}",
                description=(
                    f"Atheris found crash during fuzzing:\n"
                    f"Exception: {crash['exception_type']}\n"
                    f"Message: {str(crash['exception'])}\n"
                    f"Execution: {crash['execution']}"
                ),
                severity="critical",
                category="crash",
                file_path=str(target_path),
                metadata={
                    "crash_input_base64": crash_input_b64,
                    "crash_input_hex": crash["input"].hex(),
                    "exception_type": crash["exception_type"],
                    "stack_trace": crash["stack_trace"],
                    "execution_number": crash["execution"]
                },
                recommendation=(
                    "Review the crash stack trace and input to identify the vulnerability. "
                    "The crash input is provided in base64 and hex formats for reproduction."
                )
            )
            findings.append(finding)

            # Report crash to backend for real-time monitoring
            if self.run_id:
                try:
                    crash_report = {
                        "run_id": self.run_id,
                        "crash_id": f"crash_{idx + 1}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "crash_type": crash["exception_type"],
                        "stack_trace": crash["stack_trace"],
                        "input_file": crash_input_b64,
                        "severity": "critical",
                        "exploitability": "unknown"
                    }

                    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(
                            f"{backend_url}/fuzzing/{self.run_id}/crash",
                            json=crash_report
                        )
                        logger.debug(f"Crash report sent to backend: {crash_report['crash_id']}")
                except Exception as e:
                    logger.debug(f"Failed to post crash report to backend: {e}")

        return findings
