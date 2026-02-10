"""Harness tester module - tests and evaluates fuzz harnesses."""

import json
import subprocess
import time
from pathlib import Path

from fuzzforge_modules_sdk import (
    FuzzForgeModule,
    FuzzForgeModuleResults,
    FuzzForgeResource,
)

from module.analyzer import FeedbackGenerator
from module.feedback import (
    CompilationResult,
    CoverageMetrics,
    EvaluationSummary,
    ExecutionResult,
    FuzzingTrial,
    HarnessEvaluation,
    HarnessTestReport,
    PerformanceMetrics,
    StabilityMetrics,
)


class HarnessTesterModule(FuzzForgeModule):
    """Tests fuzz harnesses with compilation, execution, and short fuzzing trials."""

    def _run(self, resources: list[FuzzForgeResource]) -> FuzzForgeModuleResults:
        """Run harness testing on provided resources.

        :param resources: List of resources (Rust project with fuzz harnesses)
        :returns: Module execution result
        """
        self.emit_event("started", message="Beginning harness testing")

        # Configuration
        trial_duration = self.configuration.get("trial_duration_sec", 30)
        timeout_sec = self.configuration.get("execution_timeout_sec", 10)

        # Find Rust project
        project_path = self._find_rust_project(resources)
        if not project_path:
            self.emit_event("error", message="No Rust project found in resources")
            return FuzzForgeModuleResults.FAILURE

        # Find fuzz harnesses
        harnesses = self._find_fuzz_harnesses(project_path)
        if not harnesses:
            self.emit_event("error", message="No fuzz harnesses found")
            return FuzzForgeModuleResults.FAILURE

        self.emit_event(
            "found_harnesses",
            count=len(harnesses),
            harnesses=[h.name for h in harnesses],
        )

        # Test each harness
        evaluations = []
        total_harnesses = len(harnesses)

        for idx, harness in enumerate(harnesses, 1):
            self.emit_progress(
                int((idx / total_harnesses) * 90),
                status="testing",
                message=f"Testing harness {idx}/{total_harnesses}: {harness.name}",
            )

            evaluation = self._test_harness(
                project_path, harness, trial_duration, timeout_sec
            )
            evaluations.append(evaluation)

            # Emit evaluation summary
            self.emit_event(
                "harness_tested",
                harness=harness.name,
                verdict=evaluation.quality.verdict,
                score=evaluation.quality.score,
                issues=len(evaluation.quality.issues),
            )

        # Generate summary
        summary = self._generate_summary(evaluations)

        # Create report
        report = HarnessTestReport(
            harnesses=evaluations,
            summary=summary,
            test_configuration={
                "trial_duration_sec": trial_duration,
                "execution_timeout_sec": timeout_sec,
            },
        )

        # Save report
        self._save_report(report)

        self.emit_progress(100, status="completed", message="Harness testing complete")
        self.emit_event(
            "completed",
            total_harnesses=total_harnesses,
            production_ready=summary.production_ready,
            needs_improvement=summary.needs_improvement,
            broken=summary.broken,
        )

        return FuzzForgeModuleResults.SUCCESS

    def _find_rust_project(self, resources: list[FuzzForgeResource]) -> Path | None:
        """Find Rust project with Cargo.toml.

        :param resources: List of resources
        :returns: Path to Rust project or None
        """
        for resource in resources:
            cargo_toml = Path(resource.path) / "Cargo.toml"
            if cargo_toml.exists():
                return Path(resource.path)
        return None

    def _find_fuzz_harnesses(self, project_path: Path) -> list[Path]:
        """Find fuzz harnesses in project.

        :param project_path: Path to Rust project
        :returns: List of harness file paths
        """
        fuzz_dir = project_path / "fuzz" / "fuzz_targets"
        if not fuzz_dir.exists():
            return []

        harnesses = list(fuzz_dir.glob("*.rs"))
        return harnesses

    def _test_harness(
        self,
        project_path: Path,
        harness_path: Path,
        trial_duration: int,
        timeout_sec: int,
    ) -> HarnessEvaluation:
        """Test a single harness comprehensively.

        :param project_path: Path to Rust project
        :param harness_path: Path to harness file
        :param trial_duration: Duration for fuzzing trial in seconds
        :param timeout_sec: Timeout for execution test
        :returns: Harness evaluation
        """
        harness_name = harness_path.stem

        # Step 1: Compilation
        self.emit_event("compiling", harness=harness_name)
        compilation = self._test_compilation(project_path, harness_name)

        # Initialize evaluation
        evaluation = HarnessEvaluation(
            name=harness_name,
            path=str(harness_path),
            compilation=compilation,
            execution=None,
            fuzzing_trial=None,
            quality=None,  # type: ignore
        )

        # If compilation failed, generate feedback and return
        if not compilation.success:
            evaluation.quality = FeedbackGenerator.generate_quality_assessment(
                compilation_result=compilation.dict(),
                execution_result=None,
                coverage=None,
                performance=None,
                stability=None,
            )
            return evaluation

        # Step 2: Execution test
        self.emit_event("testing_execution", harness=harness_name)
        execution = self._test_execution(project_path, harness_name, timeout_sec)
        evaluation.execution = execution

        if not execution.success:
            evaluation.quality = FeedbackGenerator.generate_quality_assessment(
                compilation_result=compilation.dict(),
                execution_result=execution.dict(),
                coverage=None,
                performance=None,
                stability=None,
            )
            return evaluation

        # Step 3: Fuzzing trial
        self.emit_event("running_trial", harness=harness_name, duration=trial_duration)
        fuzzing_trial = self._run_fuzzing_trial(
            project_path, harness_name, trial_duration
        )
        evaluation.fuzzing_trial = fuzzing_trial

        # Generate quality assessment
        evaluation.quality = FeedbackGenerator.generate_quality_assessment(
            compilation_result=compilation.dict(),
            execution_result=execution.dict(),
            coverage=fuzzing_trial.coverage if fuzzing_trial else None,
            performance=fuzzing_trial.performance if fuzzing_trial else None,
            stability=fuzzing_trial.stability if fuzzing_trial else None,
        )

        return evaluation

    def _test_compilation(self, project_path: Path, harness_name: str) -> CompilationResult:
        """Test harness compilation.

        :param project_path: Path to Rust project
        :param harness_name: Name of harness to compile
        :returns: Compilation result
        """
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "fuzz", "build", harness_name],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout for compilation
            )

            compilation_time = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                # Parse warnings
                warnings = self._parse_compiler_warnings(result.stderr)
                return CompilationResult(
                    success=True, time_ms=compilation_time, warnings=warnings
                )
            else:
                # Parse errors
                errors = self._parse_compiler_errors(result.stderr)
                return CompilationResult(
                    success=False,
                    time_ms=compilation_time,
                    errors=errors,
                    stderr=result.stderr,
                )

        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                errors=["Compilation timed out after 5 minutes"],
                stderr="Timeout",
            )
        except Exception as e:
            return CompilationResult(
                success=False, errors=[f"Compilation failed: {e!s}"], stderr=str(e)
            )

    def _test_execution(
        self, project_path: Path, harness_name: str, timeout_sec: int
    ) -> ExecutionResult:
        """Test harness execution with minimal input.

        :param project_path: Path to Rust project
        :param harness_name: Name of harness
        :param timeout_sec: Timeout for execution
        :returns: Execution result
        """
        try:
            # Run with very short timeout and max runs
            result = subprocess.run(
                [
                    "cargo",
                    "fuzz",
                    "run",
                    harness_name,
                    "--",
                    "-runs=10",
                    f"-max_total_time={timeout_sec}",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=timeout_sec + 5,
            )

            # Check if it crashed immediately
            if "SUMMARY: libFuzzer: deadly signal" in result.stderr:
                return ExecutionResult(
                    success=False,
                    immediate_crash=True,
                    crash_details=self._extract_crash_info(result.stderr),
                )

            # Success if completed runs
            return ExecutionResult(success=True, runs_completed=10)

        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, timeout=True)
        except Exception as e:
            return ExecutionResult(
                success=False, immediate_crash=True, crash_details=str(e)
            )

    def _run_fuzzing_trial(
        self, project_path: Path, harness_name: str, duration_sec: int
    ) -> FuzzingTrial | None:
        """Run short fuzzing trial to gather metrics.

        :param project_path: Path to Rust project
        :param harness_name: Name of harness
        :param duration_sec: Duration to run fuzzing
        :returns: Fuzzing trial results or None if failed
        """
        try:
            result = subprocess.run(
                [
                    "cargo",
                    "fuzz",
                    "run",
                    harness_name,
                    "--",
                    f"-max_total_time={duration_sec}",
                    "-print_final_stats=1",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=duration_sec + 30,
            )

            # Parse fuzzing statistics
            stats = self._parse_fuzzing_stats(result.stderr)

            # Create metrics
            coverage = CoverageMetrics(
                initial_edges=stats.get("initial_edges", 0),
                final_edges=stats.get("cov_edges", 0),
                new_edges_found=stats.get("cov_edges", 0) - stats.get("initial_edges", 0),
                growth_rate=self._assess_coverage_growth(stats),
                percentage_estimate=self._estimate_coverage_percentage(stats),
                stagnation_time_sec=stats.get("stagnation_time"),
            )

            performance = PerformanceMetrics(
                total_execs=stats.get("total_execs", 0),
                execs_per_sec=stats.get("exec_per_sec", 0.0),
                performance_rating=self._assess_performance(stats.get("exec_per_sec", 0.0)),
            )

            stability = StabilityMetrics(
                status=self._assess_stability(stats),
                crashes_found=stats.get("crashes", 0),
                unique_crashes=stats.get("unique_crashes", 0),
                crash_rate=self._calculate_crash_rate(stats),
            )

            return FuzzingTrial(
                duration_seconds=duration_sec,
                coverage=coverage,
                performance=performance,
                stability=stability,
                trial_successful=True,
            )

        except Exception:
            return None

    def _parse_compiler_errors(self, stderr: str) -> list[str]:
        """Parse compiler error messages.

        :param stderr: Compiler stderr output
        :returns: List of error messages
        """
        errors = []
        for line in stderr.split("\n"):
            if "error:" in line or "error[" in line:
                errors.append(line.strip())
        return errors[:10]  # Limit to first 10 errors

    def _parse_compiler_warnings(self, stderr: str) -> list[str]:
        """Parse compiler warnings.

        :param stderr: Compiler stderr output
        :returns: List of warning messages
        """
        warnings = []
        for line in stderr.split("\n"):
            if "warning:" in line:
                warnings.append(line.strip())
        return warnings[:5]  # Limit to first 5 warnings

    def _extract_crash_info(self, stderr: str) -> str:
        """Extract crash information from stderr.

        :param stderr: Fuzzer stderr output
        :returns: Crash details
        """
        lines = stderr.split("\n")
        for i, line in enumerate(lines):
            if "SUMMARY:" in line or "deadly signal" in line:
                return "\n".join(lines[max(0, i - 3) : i + 5])
        return stderr[:500]  # First 500 chars if no specific crash info

    def _parse_fuzzing_stats(self, stderr: str) -> dict:
        """Parse fuzzing statistics from libFuzzer output.

        :param stderr: Fuzzer stderr output
        :returns: Dictionary of statistics
        """
        stats = {
            "total_execs": 0,
            "exec_per_sec": 0.0,
            "cov_edges": 0,
            "initial_edges": 0,
            "crashes": 0,
            "unique_crashes": 0,
        }

        lines = stderr.split("\n")

        # Find initial coverage
        for line in lines[:20]:
            if "cov:" in line:
                try:
                    cov_part = line.split("cov:")[1].split()[0]
                    stats["initial_edges"] = int(cov_part)
                    break
                except (IndexError, ValueError):
                    pass

        # Parse final stats
        for line in reversed(lines):
            if "#" in line and "cov:" in line and "exec/s:" in line:
                try:
                    # Parse line like: "#12345  cov: 891 ft: 1234 corp: 56/789b exec/s: 1507"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.startswith("#"):
                            stats["total_execs"] = int(part[1:])
                        elif part == "cov:":
                            stats["cov_edges"] = int(parts[i + 1])
                        elif part == "exec/s:":
                            stats["exec_per_sec"] = float(parts[i + 1])
                except (IndexError, ValueError):
                    pass

            # Count crashes
            if "crash-" in line or "leak-" in line or "timeout-" in line:
                stats["crashes"] += 1

        # Estimate unique crashes (simplified)
        stats["unique_crashes"] = min(stats["crashes"], 10)

        return stats

    def _assess_coverage_growth(self, stats: dict) -> str:
        """Assess coverage growth quality.

        :param stats: Fuzzing statistics
        :returns: Growth rate assessment
        """
        new_edges = stats.get("cov_edges", 0) - stats.get("initial_edges", 0)

        if new_edges == 0:
            return "none"
        elif new_edges < 50:
            return "poor"
        elif new_edges < 200:
            return "good"
        else:
            return "excellent"

    def _estimate_coverage_percentage(self, stats: dict) -> float | None:
        """Estimate coverage percentage (rough heuristic).

        :param stats: Fuzzing statistics
        :returns: Estimated percentage or None
        """
        edges = stats.get("cov_edges", 0)
        if edges == 0:
            return 0.0

        # Rough heuristic: assume medium-sized function has ~2000 edges
        # This is very approximate
        estimated = min((edges / 2000) * 100, 100)
        return round(estimated, 1)

    def _assess_performance(self, execs_per_sec: float) -> str:
        """Assess performance rating.

        :param execs_per_sec: Executions per second
        :returns: Performance rating
        """
        if execs_per_sec > 1000:
            return "excellent"
        elif execs_per_sec > 100:
            return "good"
        else:
            return "poor"

    def _assess_stability(self, stats: dict) -> str:
        """Assess stability status.

        :param stats: Fuzzing statistics
        :returns: Stability status
        """
        crashes = stats.get("crashes", 0)
        total_execs = stats.get("total_execs", 0)

        if total_execs == 0:
            return "unknown"

        crash_rate = (crashes / total_execs) * 1000

        if crash_rate > 10:
            return "crashes_frequently"
        elif crash_rate > 1:
            return "unstable"
        else:
            return "stable"

    def _calculate_crash_rate(self, stats: dict) -> float:
        """Calculate crash rate per 1000 executions.

        :param stats: Fuzzing statistics
        :returns: Crash rate
        """
        crashes = stats.get("crashes", 0)
        total = stats.get("total_execs", 0)

        if total == 0:
            return 0.0

        return (crashes / total) * 1000

    def _generate_summary(self, evaluations: list[HarnessEvaluation]) -> EvaluationSummary:
        """Generate evaluation summary.

        :param evaluations: List of harness evaluations
        :returns: Summary statistics
        """
        production_ready = sum(
            1 for e in evaluations if e.quality.verdict == "production-ready"
        )
        needs_improvement = sum(
            1 for e in evaluations if e.quality.verdict == "needs-improvement"
        )
        broken = sum(1 for e in evaluations if e.quality.verdict == "broken")

        avg_score = (
            sum(e.quality.score for e in evaluations) / len(evaluations)
            if evaluations
            else 0
        )

        # Generate recommendation
        if broken > 0:
            recommended_action = f"Fix {broken} broken harness(es) before proceeding."
        elif needs_improvement > 0:
            recommended_action = f"Improve {needs_improvement} harness(es) for better results."
        else:
            recommended_action = "All harnesses are production-ready!"

        return EvaluationSummary(
            total_harnesses=len(evaluations),
            production_ready=production_ready,
            needs_improvement=needs_improvement,
            broken=broken,
            average_score=round(avg_score, 1),
            recommended_action=recommended_action,
        )

    def _save_report(self, report: HarnessTestReport) -> None:
        """Save test report to results directory.

        :param report: Harness test report
        """
        # Save JSON report
        results_path = Path("/results/harness-evaluation.json")
        with results_path.open("w") as f:
            json.dump(report.dict(), f, indent=2)

        # Save human-readable summary
        summary_path = Path("/results/feedback-summary.md")
        with summary_path.open("w") as f:
            f.write("# Harness Testing Report\n\n")
            f.write(f"**Total Harnesses:** {report.summary.total_harnesses}\n")
            f.write(f"**Production Ready:** {report.summary.production_ready}\n")
            f.write(f"**Needs Improvement:** {report.summary.needs_improvement}\n")
            f.write(f"**Broken:** {report.summary.broken}\n")
            f.write(f"**Average Score:** {report.summary.average_score}/100\n\n")
            f.write(f"**Recommendation:** {report.summary.recommended_action}\n\n")

            f.write("## Individual Harness Results\n\n")
            for harness in report.harnesses:
                f.write(f"### {harness.name}\n\n")
                f.write(f"- **Verdict:** {harness.quality.verdict}\n")
                f.write(f"- **Score:** {harness.quality.score}/100\n\n")

                if harness.quality.strengths:
                    f.write("**Strengths:**\n")
                    for strength in harness.quality.strengths:
                        f.write(f"- {strength}\n")
                    f.write("\n")

                if harness.quality.issues:
                    f.write("**Issues:**\n")
                    for issue in harness.quality.issues:
                        f.write(f"- [{issue.severity.upper()}] {issue.message}\n")
                        f.write(f"  - **Suggestion:** {issue.suggestion}\n")
                    f.write("\n")

                if harness.quality.recommended_actions:
                    f.write("**Actions:**\n")
                    for action in harness.quality.recommended_actions:
                        f.write(f"- {action}\n")
                    f.write("\n")


# Entry point
harness_tester = HarnessTesterModule()
