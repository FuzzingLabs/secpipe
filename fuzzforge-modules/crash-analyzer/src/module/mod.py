"""Crash Analyzer module for FuzzForge.

This module analyzes crashes from cargo-fuzz, deduplicates them,
extracts stack traces, and triages them by severity.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from fuzzforge_modules_sdk.api.constants import PATH_TO_INPUTS, PATH_TO_OUTPUTS
from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResults
from fuzzforge_modules_sdk.api.modules.base import FuzzForgeModule

from module.models import Input, Output, CrashAnalysis, Severity
from module.settings import Settings

if TYPE_CHECKING:
    from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResource

logger = structlog.get_logger()


class Module(FuzzForgeModule):
    """Crash Analyzer module - analyzes and triages fuzzer crashes."""

    _settings: Settings | None
    _analyses: list[CrashAnalysis]
    _fuzz_project_path: Path | None

    def __init__(self) -> None:
        """Initialize an instance of the class."""
        name: str = "crash-analyzer"
        version: str = "0.1.0"
        FuzzForgeModule.__init__(self, name=name, version=version)
        self._settings = None
        self._analyses = []
        self._fuzz_project_path = None

    @classmethod
    def _get_input_type(cls) -> type[Input]:
        """Return the input type."""
        return Input

    @classmethod
    def _get_output_type(cls) -> type[Output]:
        """Return the output type."""
        return Output

    def _prepare(self, settings: Settings) -> None:  # type: ignore[override]
        """Prepare the module.

        :param settings: Module settings.

        """
        self._settings = settings
        logger.info("crash-analyzer preparing", settings=settings.model_dump() if settings else {})

    def _run(self, resources: list[FuzzForgeModuleResource]) -> FuzzForgeModuleResults:
        """Run the crash analyzer.

        :param resources: Input resources (fuzzing results + crashes).
        :returns: Module execution result.

        """
        logger.info("crash-analyzer starting", resource_count=len(resources))

        # Find crashes directory and fuzz project
        crashes_path = None
        for resource in resources:
            path = Path(resource.path)
            if path.is_dir():
                if path.name == "crashes" or (path / "crashes").is_dir():
                    crashes_path = path if path.name == "crashes" else path / "crashes"
                if (path / "fuzz_targets").is_dir():
                    self._fuzz_project_path = path
                if (path / "fuzz" / "fuzz_targets").is_dir():
                    self._fuzz_project_path = path / "fuzz"

        if crashes_path is None:
            # Try to find crashes in fuzzing_results.json
            for resource in resources:
                path = Path(resource.path)
                if path.name == "fuzzing_results.json" and path.exists():
                    with open(path) as f:
                        data = json.load(f)
                        if "crashes_path" in data:
                            crashes_path = Path(data["crashes_path"])
                            break

        if crashes_path is None or not crashes_path.exists():
            logger.warning("no crashes found to analyze")
            self._write_output()
            return FuzzForgeModuleResults.SUCCESS

        logger.info("analyzing crashes", path=str(crashes_path))

        # Analyze crashes per target
        for target_dir in crashes_path.iterdir():
            if target_dir.is_dir():
                target = target_dir.name
                for crash_file in target_dir.glob("crash-*"):
                    if crash_file.is_file():
                        analysis = self._analyze_crash(target, crash_file)
                        self._analyses.append(analysis)

        # Deduplicate crashes
        self._deduplicate_crashes()

        # Write output
        self._write_output()

        unique_count = sum(1 for a in self._analyses if not a.is_duplicate)
        logger.info("crash-analyzer completed",
                   total=len(self._analyses),
                   unique=unique_count)

        return FuzzForgeModuleResults.SUCCESS

    def _cleanup(self, settings: Settings) -> None:  # type: ignore[override]
        """Clean up after execution.

        :param settings: Module settings.

        """
        pass

    def _analyze_crash(self, target: str, crash_file: Path) -> CrashAnalysis:
        """Analyze a single crash.

        :param target: Name of the fuzz target.
        :param crash_file: Path to the crash input file.
        :returns: Crash analysis result.

        """
        logger.debug("analyzing crash", target=target, file=crash_file.name)

        # Read crash input
        crash_data = crash_file.read_bytes()
        input_hash = hashlib.sha256(crash_data).hexdigest()[:16]

        # Try to reproduce and get stack trace
        stack_trace = ""
        crash_type = "unknown"
        severity = Severity.UNKNOWN

        if self._fuzz_project_path:
            stack_trace, crash_type = self._reproduce_crash(target, crash_file)
            severity = self._determine_severity(crash_type, stack_trace)

        return CrashAnalysis(
            target=target,
            input_file=str(crash_file),
            input_hash=input_hash,
            input_size=len(crash_data),
            crash_type=crash_type,
            severity=severity,
            stack_trace=stack_trace,
            is_duplicate=False,
        )

    def _reproduce_crash(self, target: str, crash_file: Path) -> tuple[str, str]:
        """Reproduce a crash to get stack trace.

        :param target: Name of the fuzz target.
        :param crash_file: Path to the crash input file.
        :returns: Tuple of (stack_trace, crash_type).

        """
        if self._fuzz_project_path is None:
            return "", "unknown"

        try:
            env = os.environ.copy()
            env["RUST_BACKTRACE"] = "1"
            
            result = subprocess.run(
                [
                    "cargo", "+nightly", "fuzz", "run",
                    target,
                    str(crash_file),
                    "--",
                    "-runs=1",
                ],
                cwd=self._fuzz_project_path,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            output = result.stdout + result.stderr

            # Extract crash type
            crash_type = "unknown"
            if "heap-buffer-overflow" in output.lower():
                crash_type = "heap-buffer-overflow"
            elif "stack-buffer-overflow" in output.lower():
                crash_type = "stack-buffer-overflow"
            elif "heap-use-after-free" in output.lower():
                crash_type = "use-after-free"
            elif "null" in output.lower() and "deref" in output.lower():
                crash_type = "null-pointer-dereference"
            elif "panic" in output.lower():
                crash_type = "panic"
            elif "assertion" in output.lower():
                crash_type = "assertion-failure"
            elif "timeout" in output.lower():
                crash_type = "timeout"
            elif "out of memory" in output.lower() or "oom" in output.lower():
                crash_type = "out-of-memory"

            # Extract stack trace
            stack_lines = []
            in_stack = False
            for line in output.splitlines():
                if "SUMMARY:" in line or "ERROR:" in line:
                    in_stack = True
                if in_stack:
                    stack_lines.append(line)
                    if len(stack_lines) > 50:  # Limit stack trace length
                        break

            return "\n".join(stack_lines), crash_type

        except subprocess.TimeoutExpired:
            return "", "timeout"
        except Exception as e:
            logger.warning("failed to reproduce crash", error=str(e))
            return "", "unknown"

    def _determine_severity(self, crash_type: str, stack_trace: str) -> Severity:
        """Determine crash severity based on type and stack trace.

        :param crash_type: Type of the crash.
        :param stack_trace: Stack trace string.
        :returns: Severity level.

        """
        high_severity = [
            "heap-buffer-overflow",
            "stack-buffer-overflow",
            "use-after-free",
            "double-free",
        ]

        medium_severity = [
            "null-pointer-dereference",
            "out-of-memory",
            "integer-overflow",
        ]

        low_severity = [
            "panic",
            "assertion-failure",
            "timeout",
        ]

        if crash_type in high_severity:
            return Severity.HIGH
        elif crash_type in medium_severity:
            return Severity.MEDIUM
        elif crash_type in low_severity:
            return Severity.LOW
        else:
            return Severity.UNKNOWN

    def _deduplicate_crashes(self) -> None:
        """Mark duplicate crashes based on stack trace similarity."""
        seen_signatures: set[str] = set()

        for analysis in self._analyses:
            # Create a signature from crash type and key stack frames
            signature = self._create_signature(analysis)

            if signature in seen_signatures:
                analysis.is_duplicate = True
            else:
                seen_signatures.add(signature)

    def _create_signature(self, analysis: CrashAnalysis) -> str:
        """Create a unique signature for a crash.

        :param analysis: Crash analysis.
        :returns: Signature string.

        """
        # Use crash type + first few significant stack frames
        parts = [analysis.target, analysis.crash_type]

        # Extract function names from stack trace
        func_pattern = re.compile(r"in (\S+)")
        funcs = func_pattern.findall(analysis.stack_trace)

        # Use first 3 unique functions
        seen = set()
        for func in funcs:
            if func not in seen and not func.startswith("std::"):
                parts.append(func)
                seen.add(func)
                if len(seen) >= 3:
                    break

        return "|".join(parts)

    def _write_output(self) -> None:
        """Write the analysis results to output."""
        output_path = PATH_TO_OUTPUTS / "crash_analysis.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        unique = [a for a in self._analyses if not a.is_duplicate]
        duplicates = [a for a in self._analyses if a.is_duplicate]

        # Group by severity
        by_severity = {
            "high": [a for a in unique if a.severity == Severity.HIGH],
            "medium": [a for a in unique if a.severity == Severity.MEDIUM],
            "low": [a for a in unique if a.severity == Severity.LOW],
            "unknown": [a for a in unique if a.severity == Severity.UNKNOWN],
        }

        output_data = {
            "total_crashes": len(self._analyses),
            "unique_crashes": len(unique),
            "duplicate_crashes": len(duplicates),
            "severity_summary": {k: len(v) for k, v in by_severity.items()},
            "unique_analyses": [a.model_dump() for a in unique],
            "duplicate_analyses": [a.model_dump() for a in duplicates],
        }

        output_path.write_text(json.dumps(output_data, indent=2, default=str))
        logger.info("wrote crash analysis", path=str(output_path))
