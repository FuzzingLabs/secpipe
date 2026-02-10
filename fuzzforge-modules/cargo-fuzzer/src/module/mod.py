"""Cargo Fuzzer module for FuzzForge.

This module runs cargo-fuzz (libFuzzer) on validated Rust fuzz targets.
It takes a fuzz project with compiled harnesses and runs fuzzing for a
configurable duration, collecting crashes and statistics.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import signal
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from fuzzforge_modules_sdk.api.constants import PATH_TO_INPUTS, PATH_TO_OUTPUTS
from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResults
from fuzzforge_modules_sdk.api.modules.base import FuzzForgeModule

from module.models import Input, Output, CrashInfo, FuzzingStats, TargetResult
from module.settings import Settings

if TYPE_CHECKING:
    from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResource

logger = structlog.get_logger()


class Module(FuzzForgeModule):
    """Cargo Fuzzer module - runs cargo-fuzz with libFuzzer on Rust targets."""

    _settings: Settings | None
    _fuzz_project_path: Path | None
    _target_results: list[TargetResult]
    _crashes_path: Path | None

    def __init__(self) -> None:
        """Initialize an instance of the class."""
        name: str = "cargo-fuzzer"
        version: str = "0.1.0"
        FuzzForgeModule.__init__(self, name=name, version=version)
        self._settings = None
        self._fuzz_project_path = None
        self._target_results = []
        self._crashes_path = None

    @classmethod
    def _get_input_type(cls) -> type[Input]:
        """Return the input type."""
        return Input

    @classmethod
    def _get_output_type(cls) -> type[Output]:
        """Return the output type."""
        return Output

    def _prepare(self, settings: Settings) -> None:  # type: ignore[override]
        """Prepare the module with settings.

        :param settings: Module settings.

        """
        self._settings = settings
        logger.info("cargo-fuzzer preparing", settings=settings.model_dump() if settings else {})

    def _run(self, resources: list[FuzzForgeModuleResource]) -> FuzzForgeModuleResults:
        """Run the fuzzer.

        :param resources: Input resources (fuzz project + source).
        :returns: Module execution result.

        """
        logger.info("cargo-fuzzer starting", resource_count=len(resources))
        
        # Emit initial progress
        self.emit_progress(0, status="initializing", message="Setting up fuzzing environment")
        self.emit_event("module_started", resource_count=len(resources))

        # Setup the fuzzing environment
        if not self._setup_environment(resources):
            self.emit_progress(100, status="failed", message="Failed to setup environment")
            return FuzzForgeModuleResults.FAILURE

        # Get list of fuzz targets
        targets = self._get_fuzz_targets()
        if not targets:
            logger.error("no fuzz targets found")
            self.emit_progress(100, status="failed", message="No fuzz targets found")
            return FuzzForgeModuleResults.FAILURE

        # Filter targets if specific ones were requested
        if self._settings and self._settings.targets:
            requested = set(self._settings.targets)
            targets = [t for t in targets if t in requested]
            if not targets:
                logger.error("none of the requested targets found", requested=list(requested))
                self.emit_progress(100, status="failed", message="Requested targets not found")
                return FuzzForgeModuleResults.FAILURE

        logger.info("found fuzz targets", targets=targets)
        self.emit_event("targets_found", targets=targets, count=len(targets))

        # Setup output directories
        self._crashes_path = PATH_TO_OUTPUTS / "crashes"
        self._crashes_path.mkdir(parents=True, exist_ok=True)

        # Run fuzzing on each target
        # max_duration=0 means infinite/continuous mode
        max_duration = self._settings.max_duration if self._settings else 60
        is_continuous = max_duration == 0
        
        if is_continuous:
            # Continuous mode: cycle through targets indefinitely
            # Each target runs for 60 seconds before moving to next
            duration_per_target = 60
        else:
            duration_per_target = max_duration // max(len(targets), 1)
        total_crashes = 0

        # In continuous mode, loop forever; otherwise loop once
        round_num = 0
        while True:
            round_num += 1
            
            for i, target in enumerate(targets):
                if is_continuous:
                    progress_msg = f"Round {round_num}: Fuzzing {target}"
                else:
                    progress_msg = f"Fuzzing target {i+1}/{len(targets)}"
                
                progress = int((i / len(targets)) * 100) if not is_continuous else 50
                self.emit_progress(
                    progress,
                    status="running",
                    message=progress_msg,
                    current_task=target,
                    metrics={
                        "targets_completed": i,
                        "total_targets": len(targets),
                        "crashes_found": total_crashes,
                        "round": round_num if is_continuous else 1,
                    }
                )
                self.emit_event("target_started", target=target, index=i, total=len(targets), round=round_num)
                
                result = self._fuzz_target(target, duration_per_target)
                self._target_results.append(result)
                total_crashes += len(result.crashes)
                
                # Emit target completion
                self.emit_event(
                    "target_completed",
                    target=target,
                    crashes=len(result.crashes),
                    executions=result.stats.total_executions if result.stats else 0,
                    coverage=result.stats.coverage_edges if result.stats else 0,
                )
                
                logger.info("target completed",
                           target=target,
                           crashes=len(result.crashes),
                           execs=result.stats.total_executions if result.stats else 0)
            
            # Exit loop if not continuous mode
            if not is_continuous:
                break

        # Write output
        self._write_output()
        
        # Emit final progress
        self.emit_progress(
            100,
            status="completed",
            message=f"Fuzzing completed. Found {total_crashes} crashes.",
            metrics={
                "targets_fuzzed": len(self._target_results),
                "total_crashes": total_crashes,
                "total_executions": sum(r.stats.total_executions for r in self._target_results if r.stats),
            }
        )
        self.emit_event("module_completed", total_crashes=total_crashes, targets_fuzzed=len(targets))

        logger.info("cargo-fuzzer completed",
                   targets=len(self._target_results),
                   total_crashes=total_crashes)

        return FuzzForgeModuleResults.SUCCESS

    def _cleanup(self, settings: Settings) -> None:  # type: ignore[override]
        """Clean up after execution.

        :param settings: Module settings.

        """
        pass

    def _setup_environment(self, resources: list[FuzzForgeModuleResource]) -> bool:
        """Setup the fuzzing environment.

        :param resources: Input resources.
        :returns: True if setup successful.

        """
        import shutil
        
        # Find fuzz project in resources
        source_fuzz_project = None
        source_project_root = None
        
        for resource in resources:
            path = Path(resource.path)
            if path.is_dir():
                # Check for fuzz subdirectory
                fuzz_dir = path / "fuzz"
                if fuzz_dir.is_dir() and (fuzz_dir / "Cargo.toml").exists():
                    source_fuzz_project = fuzz_dir
                    source_project_root = path
                    break
                # Or direct fuzz project
                if (path / "Cargo.toml").exists() and (path / "fuzz_targets").is_dir():
                    source_fuzz_project = path
                    source_project_root = path.parent
                    break

        if source_fuzz_project is None:
            logger.error("no fuzz project found in resources")
            return False

        # Copy project to writable location since /data/input is read-only
        # and cargo-fuzz needs to write corpus, artifacts, and build cache
        work_dir = Path("/tmp/fuzz-work")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        
        # Copy the entire project root
        work_project = work_dir / source_project_root.name
        shutil.copytree(source_project_root, work_project, dirs_exist_ok=True)
        
        # Update fuzz_project_path to point to the copied location
        relative_fuzz = source_fuzz_project.relative_to(source_project_root)
        self._fuzz_project_path = work_project / relative_fuzz
        
        logger.info("using fuzz project", path=str(self._fuzz_project_path))
        return True

    def _get_fuzz_targets(self) -> list[str]:
        """Get list of fuzz target names.

        :returns: List of target names.

        """
        if self._fuzz_project_path is None:
            return []

        targets = []
        fuzz_targets_dir = self._fuzz_project_path / "fuzz_targets"

        if fuzz_targets_dir.is_dir():
            for rs_file in fuzz_targets_dir.glob("*.rs"):
                targets.append(rs_file.stem)

        return targets

    def _fuzz_target(self, target: str, duration: int) -> TargetResult:
        """Run fuzzing on a single target.

        :param target: Name of the fuzz target.
        :param duration: Maximum duration in seconds.
        :returns: Fuzzing result for this target.

        """
        logger.info("fuzzing target", target=target, duration=duration)

        crashes: list[CrashInfo] = []
        stats = FuzzingStats()

        if self._fuzz_project_path is None:
            return TargetResult(target=target, crashes=crashes, stats=stats)

        # Create corpus directory for this target
        corpus_dir = self._fuzz_project_path / "corpus" / target
        corpus_dir.mkdir(parents=True, exist_ok=True)

        # Build the command
        cmd = [
            "cargo", "+nightly", "fuzz", "run",
            target,
            "--",
        ]
        
        # Add time limit
        if duration > 0:
            cmd.append(f"-max_total_time={duration}")
        
        # Use fork mode to continue after crashes
        # This makes libFuzzer restart worker after crash instead of exiting
        cmd.append("-fork=1")
        cmd.append("-ignore_crashes=1")
        cmd.append("-print_final_stats=1")

        # Add jobs if specified
        if self._settings and self._settings.jobs > 1:
            cmd.extend([f"-jobs={self._settings.jobs}"])

        try:
            env = os.environ.copy()
            env["CARGO_INCREMENTAL"] = "0"
            
            process = subprocess.Popen(
                cmd,
                cwd=self._fuzz_project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            output_lines = []
            start_time = time.time()
            last_metrics_emit = 0.0
            current_execs = 0
            current_cov = 0
            current_exec_s = 0
            crash_count = 0

            # Read output with timeout (skip timeout check in infinite mode)
            while True:
                if process.poll() is not None:
                    break

                elapsed = time.time() - start_time
                # Only enforce timeout if duration > 0 (not infinite mode)
                if duration > 0 and elapsed > duration + 30:  # Grace period
                    logger.warning("fuzzer timeout, terminating", target=target)
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    break

                try:
                    if process.stdout:
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line)
                            
                            # Parse real-time metrics from libFuzzer output
                            # Example: "#12345	NEW    cov: 100 ft: 50 corp: 25/1Kb exec/s: 1000"
                            exec_match = re.search(r"#(\d+)", line)
                            if exec_match:
                                current_execs = int(exec_match.group(1))
                            
                            cov_match = re.search(r"cov:\s*(\d+)", line)
                            if cov_match:
                                current_cov = int(cov_match.group(1))
                            
                            exec_s_match = re.search(r"exec/s:\s*(\d+)", line)
                            if exec_s_match:
                                current_exec_s = int(exec_s_match.group(1))
                            
                            # Check for crash indicators
                            if "SUMMARY:" in line or "ERROR:" in line or "crash-" in line.lower():
                                crash_count += 1
                                self.emit_event(
                                    "crash_detected",
                                    target=target,
                                    crash_number=crash_count,
                                    line=line.strip(),
                                )
                                logger.debug("fuzzer output", line=line.strip())
                            
                            # Emit metrics periodically (every 2 seconds)
                            if elapsed - last_metrics_emit >= 2.0:
                                last_metrics_emit = elapsed
                                self.emit_event(
                                    "metrics",
                                    target=target,
                                    executions=current_execs,
                                    coverage=current_cov,
                                    exec_per_sec=current_exec_s,
                                    crashes=crash_count,
                                    elapsed_seconds=int(elapsed),
                                    remaining_seconds=max(0, duration - int(elapsed)),
                                )
                                
                except Exception:
                    pass

            # Parse statistics from output
            stats = self._parse_fuzzer_stats(output_lines)

            # Collect crashes
            crashes = self._collect_crashes(target)
            
            # Emit final event for this target if crashes were found
            if crashes:
                self.emit_event(
                    "crashes_collected",
                    target=target,
                    count=len(crashes),
                    paths=[c.file_path for c in crashes],
                )

        except FileNotFoundError:
            logger.error("cargo-fuzz not found, please install with: cargo install cargo-fuzz")
            stats.error = "cargo-fuzz not installed"
            self.emit_event("error", target=target, message="cargo-fuzz not installed")
        except Exception as e:
            logger.exception("fuzzing error", target=target, error=str(e))
            stats.error = str(e)
            self.emit_event("error", target=target, message=str(e))

        return TargetResult(target=target, crashes=crashes, stats=stats)

    def _parse_fuzzer_stats(self, output_lines: list[str]) -> FuzzingStats:
        """Parse fuzzer output for statistics.

        :param output_lines: Lines of fuzzer output.
        :returns: Parsed statistics.

        """
        stats = FuzzingStats()
        full_output = "".join(output_lines)

        # Parse libFuzzer stats
        # Example: "#12345	DONE   cov: 100 ft: 50 corp: 25/1Kb exec/s: 1000"
        exec_match = re.search(r"#(\d+)", full_output)
        if exec_match:
            stats.total_executions = int(exec_match.group(1))

        cov_match = re.search(r"cov:\s*(\d+)", full_output)
        if cov_match:
            stats.coverage_edges = int(cov_match.group(1))

        corp_match = re.search(r"corp:\s*(\d+)", full_output)
        if corp_match:
            stats.corpus_size = int(corp_match.group(1))

        exec_s_match = re.search(r"exec/s:\s*(\d+)", full_output)
        if exec_s_match:
            stats.executions_per_second = int(exec_s_match.group(1))

        return stats

    def _collect_crashes(self, target: str) -> list[CrashInfo]:
        """Collect crash files from fuzzer output.

        :param target: Name of the fuzz target.
        :returns: List of crash info.

        """
        crashes: list[CrashInfo] = []

        if self._fuzz_project_path is None or self._crashes_path is None:
            return crashes

        # Check for crashes in the artifacts directory
        artifacts_dir = self._fuzz_project_path / "artifacts" / target

        if artifacts_dir.is_dir():
            for crash_file in artifacts_dir.glob("crash-*"):
                if crash_file.is_file():
                    # Copy crash to output
                    output_crash = self._crashes_path / target
                    output_crash.mkdir(parents=True, exist_ok=True)
                    dest = output_crash / crash_file.name
                    shutil.copy2(crash_file, dest)

                    # Read crash input
                    crash_data = crash_file.read_bytes()

                    crash_info = CrashInfo(
                        file_path=str(dest),
                        input_hash=crash_file.name,
                        input_size=len(crash_data),
                    )
                    crashes.append(crash_info)

                    logger.info("found crash", target=target, file=crash_file.name)

        return crashes

    def _write_output(self) -> None:
        """Write the fuzzing results to output."""
        output_path = PATH_TO_OUTPUTS / "fuzzing_results.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_crashes = sum(len(r.crashes) for r in self._target_results)
        total_execs = sum(r.stats.total_executions for r in self._target_results if r.stats)

        output_data = {
            "fuzz_project": str(self._fuzz_project_path),
            "targets_fuzzed": len(self._target_results),
            "total_crashes": total_crashes,
            "total_executions": total_execs,
            "crashes_path": str(self._crashes_path),
            "results": [
                {
                    "target": r.target,
                    "crashes": [c.model_dump() for c in r.crashes],
                    "stats": r.stats.model_dump() if r.stats else None,
                }
                for r in self._target_results
            ],
        }

        output_path.write_text(json.dumps(output_data, indent=2))
        logger.info("wrote fuzzing results", path=str(output_path))
