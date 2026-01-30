"""
Cargo Fuzzer Module

Reusable module for fuzzing Rust code using cargo-fuzz (libFuzzer).
Discovers and fuzzes user-provided Rust targets with fuzz_target!() macros.
"""

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding

logger = logging.getLogger(__name__)


class CargoFuzzer(BaseModule):
    """
    Cargo-fuzz (libFuzzer) fuzzer module for Rust code.

    Discovers fuzz targets in user's Rust project and runs cargo-fuzz
    to find crashes, undefined behavior, and memory safety issues.
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="cargo_fuzz",
            version="0.11.2",
            description="Fuzz Rust code using cargo-fuzz with libFuzzer backend",
            author="FuzzForge Team",
            category="fuzzer",
            tags=["fuzzing", "rust", "cargo-fuzz", "libfuzzer", "memory-safety"],
            input_schema={
                "type": "object",
                "properties": {
                    "target_name": {
                        "type": "string",
                        "description": "Fuzz target name (auto-discovered if not specified)"
                    },
                    "max_iterations": {
                        "type": "integer",
                        "default": 1000000,
                        "description": "Maximum fuzzing iterations"
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "default": 1800,
                        "description": "Fuzzing timeout in seconds"
                    },
                    "sanitizer": {
                        "type": "string",
                        "enum": ["address", "memory", "undefined"],
                        "default": "address",
                        "description": "Sanitizer to use (address, memory, undefined)"
                    }
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "description": "Crashes and memory safety issues found"
                    },
                    "summary": {
                        "type": "object",
                        "description": "Fuzzing execution summary"
                    }
                }
            }
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration"""
        max_iterations = config.get("max_iterations", 1000000)
        if not isinstance(max_iterations, int) or max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")

        timeout = config.get("timeout_seconds", 1800)
        if not isinstance(timeout, int) or timeout < 1:
            raise ValueError("timeout_seconds must be a positive integer")

        sanitizer = config.get("sanitizer", "address")
        if sanitizer not in ["address", "memory", "undefined"]:
            raise ValueError("sanitizer must be one of: address, memory, undefined")

        return True

    async def execute(
        self,
        config: Dict[str, Any],
        workspace: Path,
        stats_callback: Optional[Callable] = None
    ) -> ModuleResult:
        """
        Execute cargo-fuzz on user's Rust code.

        Args:
            config: Fuzzer configuration
            workspace: Path to workspace directory containing Rust project
            stats_callback: Optional callback for real-time stats updates

        Returns:
            ModuleResult containing findings and summary
        """
        self.start_timer()

        try:
            # Validate inputs
            self.validate_config(config)
            self.validate_workspace(workspace)

            logger.info(f"Running cargo-fuzz on {workspace}")

            # Step 1: Discover fuzz targets
            targets = await self._discover_fuzz_targets(workspace)
            if not targets:
                return self.create_result(
                    findings=[],
                    status="failed",
                    error="No fuzz targets found. Expected fuzz targets in fuzz/fuzz_targets/"
                )

            # Get target name from config or use first discovered target
            target_name = config.get("target_name")
            if not target_name:
                target_name = targets[0]
                logger.info(f"No target specified, using first discovered target: {target_name}")
            elif target_name not in targets:
                return self.create_result(
                    findings=[],
                    status="failed",
                    error=f"Target '{target_name}' not found. Available targets: {', '.join(targets)}"
                )

            # Step 2: Build fuzz target
            logger.info(f"Building fuzz target: {target_name}")
            build_success = await self._build_fuzz_target(workspace, target_name, config)
            if not build_success:
                return self.create_result(
                    findings=[],
                    status="failed",
                    error=f"Failed to build fuzz target: {target_name}"
                )

            # Step 3: Run fuzzing
            logger.info(f"Starting fuzzing: {target_name}")
            findings, stats = await self._run_fuzzing(
                workspace,
                target_name,
                config,
                stats_callback
            )

            # Step 4: Parse crash artifacts
            crash_findings = await self._parse_crash_artifacts(workspace, target_name)
            findings.extend(crash_findings)

            logger.info(f"Fuzzing completed: {len(findings)} crashes found")

            return self.create_result(
                findings=findings,
                status="success",
                summary=stats
            )

        except Exception as e:
            logger.error(f"Cargo fuzzer failed: {e}")
            return self.create_result(
                findings=[],
                status="failed",
                error=str(e)
            )

    async def _discover_fuzz_targets(self, workspace: Path) -> List[str]:
        """
        Discover fuzz targets in the project.

        Looks for fuzz targets in fuzz/fuzz_targets/ directory.
        """
        fuzz_targets_dir = workspace / "fuzz" / "fuzz_targets"
        if not fuzz_targets_dir.exists():
            logger.warning(f"No fuzz targets directory found: {fuzz_targets_dir}")
            return []

        targets = []
        for file in fuzz_targets_dir.glob("*.rs"):
            target_name = file.stem
            targets.append(target_name)
            logger.info(f"Discovered fuzz target: {target_name}")

        return targets

    async def _build_fuzz_target(
        self,
        workspace: Path,
        target_name: str,
        config: Dict[str, Any]
    ) -> bool:
        """Build the fuzz target with instrumentation"""
        try:
            sanitizer = config.get("sanitizer", "address")

            # Build command
            cmd = [
                "cargo", "fuzz", "build",
                target_name,
                f"--sanitizer={sanitizer}"
            ]

            logger.debug(f"Build command: {' '.join(cmd)}")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Build failed: {stderr.decode()}")
                return False

            logger.info("Build successful")
            return True

        except Exception as e:
            logger.error(f"Build error: {e}")
            return False

    async def _run_fuzzing(
        self,
        workspace: Path,
        target_name: str,
        config: Dict[str, Any],
        stats_callback: Optional[Callable]
    ) -> tuple[List[ModuleFinding], Dict[str, Any]]:
        """
        Run cargo-fuzz and collect statistics.

        Returns:
            Tuple of (findings, stats_dict)
        """
        max_iterations = config.get("max_iterations", 1000000)
        timeout_seconds = config.get("timeout_seconds", 1800)
        sanitizer = config.get("sanitizer", "address")

        findings = []
        stats = {
            "total_executions": 0,
            "crashes_found": 0,
            "corpus_size": 0,
            "coverage": 0.0,
            "execution_time": 0.0
        }

        try:
            # Cargo fuzz run command
            cmd = [
                "cargo", "fuzz", "run",
                target_name,
                f"--sanitizer={sanitizer}",
                "--",
                f"-runs={max_iterations}",
                f"-max_total_time={timeout_seconds}"
            ]

            logger.debug(f"Fuzz command: {' '.join(cmd)}")

            start_time = time.time()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Monitor output and extract stats
            last_stats_time = time.time()
            async for line in proc.stdout:
                line_str = line.decode('utf-8', errors='ignore').strip()

                # Parse libFuzzer stats
                # Example: "#12345	NEW    cov: 123 ft: 456 corp: 10/234b"
                stats_match = re.match(r'#(\d+)\s+.*cov:\s*(\d+).*corp:\s*(\d+)', line_str)
                if stats_match:
                    execs = int(stats_match.group(1))
                    cov = int(stats_match.group(2))
                    corp = int(stats_match.group(3))

                    stats["total_executions"] = execs
                    stats["coverage"] = float(cov)
                    stats["corpus_size"] = corp
                    stats["execution_time"] = time.time() - start_time

                    # Invoke stats callback for real-time monitoring
                    if stats_callback and time.time() - last_stats_time >= 0.5:
                        await stats_callback({
                            "total_execs": execs,
                            "execs_per_sec": execs / stats["execution_time"] if stats["execution_time"] > 0 else 0,
                            "crashes": stats["crashes_found"],
                            "coverage": cov,
                            "corpus_size": corp,
                            "elapsed_time": int(stats["execution_time"])
                        })
                        last_stats_time = time.time()

                # Detect crash line
                if "SUMMARY:" in line_str or "ERROR:" in line_str:
                    logger.info(f"Detected crash: {line_str}")
                    stats["crashes_found"] += 1

            await proc.wait()
            stats["execution_time"] = time.time() - start_time

            # Send final stats update
            if stats_callback:
                await stats_callback({
                    "total_execs": stats["total_executions"],
                    "execs_per_sec": stats["total_executions"] / stats["execution_time"] if stats["execution_time"] > 0 else 0,
                    "crashes": stats["crashes_found"],
                    "coverage": stats["coverage"],
                    "corpus_size": stats["corpus_size"],
                    "elapsed_time": int(stats["execution_time"])
                })

            logger.info(
                f"Fuzzing completed: {stats['total_executions']} execs, "
                f"{stats['crashes_found']} crashes"
            )

        except Exception as e:
            logger.error(f"Fuzzing error: {e}")

        return findings, stats

    async def _parse_crash_artifacts(
        self,
        workspace: Path,
        target_name: str
    ) -> List[ModuleFinding]:
        """
        Parse crash artifacts from fuzz/artifacts directory.

        Cargo-fuzz stores crashes in: fuzz/artifacts/<target_name>/
        """
        findings = []
        artifacts_dir = workspace / "fuzz" / "artifacts" / target_name

        if not artifacts_dir.exists():
            logger.info("No crash artifacts found")
            return findings

        # Find all crash files
        for crash_file in artifacts_dir.glob("crash-*"):
            try:
                finding = await self._analyze_crash(workspace, target_name, crash_file)
                if finding:
                    findings.append(finding)
            except Exception as e:
                logger.warning(f"Failed to analyze crash {crash_file}: {e}")

        logger.info(f"Parsed {len(findings)} crash artifacts")
        return findings

    async def _analyze_crash(
        self,
        workspace: Path,
        target_name: str,
        crash_file: Path
    ) -> Optional[ModuleFinding]:
        """
        Analyze a single crash file.

        Runs cargo-fuzz with the crash input to reproduce and get stack trace.
        """
        try:
            # Read crash input
            crash_input = crash_file.read_bytes()

            # Reproduce crash to get stack trace
            cmd = [
                "cargo", "fuzz", "run",
                target_name,
                str(crash_file)
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "RUST_BACKTRACE": "1"}
            )

            stdout, _ = await proc.communicate()
            output = stdout.decode('utf-8', errors='ignore')

            # Parse stack trace and error type
            error_type = "Unknown Crash"
            stack_trace = output

            # Extract error type
            if "SEGV" in output:
                error_type = "Segmentation Fault"
                severity = "critical"
            elif "heap-use-after-free" in output:
                error_type = "Use After Free"
                severity = "critical"
            elif "heap-buffer-overflow" in output:
                error_type = "Heap Buffer Overflow"
                severity = "critical"
            elif "stack-buffer-overflow" in output:
                error_type = "Stack Buffer Overflow"
                severity = "high"
            elif "panic" in output.lower():
                error_type = "Panic"
                severity = "medium"
            else:
                severity = "high"

            # Create finding
            finding = self.create_finding(
                title=f"Crash: {error_type} in {target_name}",
                description=f"Cargo-fuzz discovered a crash in target '{target_name}'. "
                           f"Error type: {error_type}. "
                           f"Input size: {len(crash_input)} bytes.",
                severity=severity,
                category="crash",
                file_path=f"fuzz/fuzz_targets/{target_name}.rs",
                code_snippet=stack_trace[:500],
                recommendation="Review the crash details and fix the underlying bug. "
                              "Use AddressSanitizer to identify memory safety issues. "
                              "Consider adding bounds checks or using safer APIs.",
                metadata={
                    "error_type": error_type,
                    "crash_file": crash_file.name,
                    "input_size": len(crash_input),
                    "reproducer": crash_file.name,
                    "stack_trace": stack_trace
                }
            )

            return finding

        except Exception as e:
            logger.warning(f"Failed to analyze crash {crash_file}: {e}")
            return None
