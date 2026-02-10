"""Feedback generator with actionable suggestions for AI agents."""

from module.feedback import (
    CoverageMetrics,
    FeedbackCategory,
    FeedbackIssue,
    FeedbackSeverity,
    PerformanceMetrics,
    QualityAssessment,
    StabilityMetrics,
)


class FeedbackGenerator:
    """Generates actionable feedback based on harness test results."""

    @staticmethod
    def analyze_compilation(
        compilation_result: dict,
    ) -> tuple[list[FeedbackIssue], list[str]]:
        """Analyze compilation results and generate feedback.

        :param compilation_result: Compilation output and errors
        :returns: Tuple of (issues, strengths)
        """
        issues = []
        strengths = []

        if not compilation_result.get("success"):
            errors = compilation_result.get("errors", [])
            
            for error in errors:
                # Analyze specific error types
                if "cannot find" in error.lower():
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.COMPILATION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="undefined_variable",
                            message=f"Compilation error: {error}",
                            suggestion="Check variable names match the function signature. Use the exact names from fuzzable_functions.json.",
                            details={"error": error},
                        )
                    )
                elif "mismatched types" in error.lower():
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.COMPILATION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="type_mismatch",
                            message=f"Type mismatch: {error}",
                            suggestion="Check the function expects the types you're passing. Convert fuzzer input to the correct type (e.g., &[u8] to &str with from_utf8).",
                            details={"error": error},
                        )
                    )
                elif "trait" in error.lower() and "not implemented" in error.lower():
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.COMPILATION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="trait_not_implemented",
                            message=f"Trait not implemented: {error}",
                            suggestion="Ensure you're using the correct types. Some functions require specific trait implementations.",
                            details={"error": error},
                        )
                    )
                else:
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.COMPILATION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="compilation_error",
                            message=f"Compilation failed: {error}",
                            suggestion="Review the error message and fix syntax/type issues. Check function signatures in the source code.",
                            details={"error": error},
                        )
                    )
        else:
            strengths.append("Compiles successfully")
            
            # Check for warnings
            warnings = compilation_result.get("warnings", [])
            if warnings:
                for warning in warnings[:3]:  # Limit to 3 most important
                    if "unused" in warning.lower():
                        issues.append(
                            FeedbackIssue(
                                category=FeedbackCategory.CODE_QUALITY,
                                severity=FeedbackSeverity.INFO,
                                type="unused_variable",
                                message=f"Code quality: {warning}",
                                suggestion="Remove unused variables or use underscore prefix (_variable) to suppress warning.",
                                details={"warning": warning},
                            )
                        )

        return issues, strengths

    @staticmethod
    def analyze_execution(
        execution_result: dict,
    ) -> tuple[list[FeedbackIssue], list[str]]:
        """Analyze execution results.

        :param execution_result: Execution test results
        :returns: Tuple of (issues, strengths)
        """
        issues = []
        strengths = []

        if not execution_result.get("success"):
            if execution_result.get("immediate_crash"):
                crash_details = execution_result.get("crash_details", "")
                
                if "stack overflow" in crash_details.lower():
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.EXECUTION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="stack_overflow",
                            message="Harness crashes immediately with stack overflow",
                            suggestion="Check for infinite recursion or large stack allocations. Use heap allocation (Box, Vec) for large data structures.",
                            details={"crash": crash_details},
                        )
                    )
                elif "panic" in crash_details.lower():
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.EXECUTION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="panic_on_start",
                            message="Harness panics immediately",
                            suggestion="Check initialization code. Ensure required resources are available and input validation doesn't panic on empty input.",
                            details={"crash": crash_details},
                        )
                    )
                else:
                    issues.append(
                        FeedbackIssue(
                            category=FeedbackCategory.EXECUTION,
                            severity=FeedbackSeverity.CRITICAL,
                            type="immediate_crash",
                            message=f"Harness crashes immediately: {crash_details}",
                            suggestion="Debug the harness initialization. Add error handling and check for null/invalid pointers.",
                            details={"crash": crash_details},
                        )
                    )
                    
            elif execution_result.get("timeout"):
                issues.append(
                    FeedbackIssue(
                        category=FeedbackCategory.EXECUTION,
                        severity=FeedbackSeverity.CRITICAL,
                        type="infinite_loop",
                        message="Harness times out - likely infinite loop",
                        suggestion="Check for loops that depend on fuzzer input. Add iteration limits or timeout mechanisms.",
                        details={},
                    )
                )
        else:
            strengths.append("Executes without crashing")

        return issues, strengths

    @staticmethod
    def analyze_coverage(
        coverage: CoverageMetrics,
    ) -> tuple[list[FeedbackIssue], list[str]]:
        """Analyze coverage metrics.

        :param coverage: Coverage metrics from fuzzing trial
        :returns: Tuple of (issues, strengths)
        """
        issues = []
        strengths = []

        # No coverage growth
        if coverage.new_edges_found == 0:
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.COVERAGE,
                    severity=FeedbackSeverity.CRITICAL,
                    type="no_coverage",
                    message="No coverage detected - harness may not be using fuzzer input",
                    suggestion="Ensure you're actually calling the target function with fuzzer-provided data. Check that 'data' parameter is passed to the function being fuzzed.",
                    details={"initial_edges": coverage.initial_edges},
                )
            )
        # Very low coverage
        elif coverage.growth_rate == "none" or (
            coverage.percentage_estimate and coverage.percentage_estimate < 5
        ):
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.COVERAGE,
                    severity=FeedbackSeverity.WARNING,
                    type="very_low_coverage",
                    message=f"Very low coverage: ~{coverage.percentage_estimate}%",
                    suggestion="Harness may not be reaching the target code. Verify you're calling the correct entry point function. Check if there's input validation that rejects all fuzzer data.",
                    details={
                        "percentage": coverage.percentage_estimate,
                        "edges": coverage.final_edges,
                    },
                )
            )
        # Low coverage
        elif coverage.growth_rate == "poor" or (
            coverage.percentage_estimate and coverage.percentage_estimate < 20
        ):
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.COVERAGE,
                    severity=FeedbackSeverity.WARNING,
                    type="low_coverage",
                    message=f"Low coverage: {coverage.percentage_estimate}% - not exploring enough code paths",
                    suggestion="Try fuzzing multiple entry points or remove restrictive input validation. Consider using a dictionary for structured inputs.",
                    details={
                        "percentage": coverage.percentage_estimate,
                        "new_edges": coverage.new_edges_found,
                    },
                )
            )
        # Good coverage
        elif coverage.growth_rate in ["good", "excellent"]:
            if coverage.percentage_estimate and coverage.percentage_estimate > 50:
                strengths.append(
                    f"Excellent coverage: {coverage.percentage_estimate}% of target code reached"
                )
            else:
                strengths.append("Good coverage growth - harness is exploring code paths")

        # Coverage stagnation
        if (
            coverage.stagnation_time_sec
            and coverage.stagnation_time_sec < 10
            and coverage.final_edges < 500
        ):
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.COVERAGE,
                    severity=FeedbackSeverity.INFO,
                    type="early_stagnation",
                    message=f"Coverage stopped growing after {coverage.stagnation_time_sec}s",
                    suggestion="Harness may be hitting input validation barriers. Consider fuzzing with a seed corpus of valid inputs.",
                    details={"stagnation_time": coverage.stagnation_time_sec},
                )
            )

        return issues, strengths

    @staticmethod
    def analyze_performance(
        performance: PerformanceMetrics,
    ) -> tuple[list[FeedbackIssue], list[str]]:
        """Analyze performance metrics.

        :param performance: Performance metrics from fuzzing trial
        :returns: Tuple of (issues, strengths)
        """
        issues = []
        strengths = []

        execs_per_sec = performance.execs_per_sec

        # Very slow execution
        if execs_per_sec < 10:
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.PERFORMANCE,
                    severity=FeedbackSeverity.CRITICAL,
                    type="extremely_slow",
                    message=f"Extremely slow: {execs_per_sec:.1f} execs/sec",
                    suggestion="Remove file I/O, network operations, or expensive computations from the harness loop. Move setup code outside the fuzz target function.",
                    details={"execs_per_sec": execs_per_sec},
                )
            )
        # Slow execution
        elif execs_per_sec < 100:
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.PERFORMANCE,
                    severity=FeedbackSeverity.WARNING,
                    type="slow_execution",
                    message=f"Slow execution: {execs_per_sec:.1f} execs/sec (expected 500+)",
                    suggestion="Optimize harness: avoid allocations in hot path, reuse buffers, remove logging. Profile to find bottlenecks.",
                    details={"execs_per_sec": execs_per_sec},
                )
            )
        # Good performance
        elif execs_per_sec > 1000:
            strengths.append(f"Excellent performance: {execs_per_sec:.0f} execs/sec")
        elif execs_per_sec > 500:
            strengths.append(f"Good performance: {execs_per_sec:.0f} execs/sec")

        return issues, strengths

    @staticmethod
    def analyze_stability(
        stability: StabilityMetrics,
    ) -> tuple[list[FeedbackIssue], list[str]]:
        """Analyze stability metrics.

        :param stability: Stability metrics from fuzzing trial
        :returns: Tuple of (issues, strengths)
        """
        issues = []
        strengths = []

        if stability.status == "crashes_frequently":
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.STABILITY,
                    severity=FeedbackSeverity.WARNING,
                    type="unstable_frequent_crashes",
                    message=f"Harness crashes frequently: {stability.crash_rate:.1f} crashes per 1000 execs",
                    suggestion="This might be expected if testing buggy code. If not, add error handling for edge cases or invalid inputs.",
                    details={
                        "crashes": stability.crashes_found,
                        "crash_rate": stability.crash_rate,
                    },
                )
            )
        elif stability.status == "hangs":
            issues.append(
                FeedbackIssue(
                    category=FeedbackCategory.STABILITY,
                    severity=FeedbackSeverity.WARNING,
                    type="hangs_detected",
                    message=f"Harness hangs: {stability.hangs_found} detected",
                    suggestion="Add timeouts to prevent infinite loops. Check for blocking operations or resource exhaustion.",
                    details={"hangs": stability.hangs_found},
                )
            )
        elif stability.status == "stable":
            strengths.append("Stable execution - no crashes or hangs")

        # Finding crashes can be good!
        if stability.unique_crashes > 0 and stability.status != "crashes_frequently":
            strengths.append(
                f"Found {stability.unique_crashes} potential bugs during trial!"
            )

        return issues, strengths

    @staticmethod
    def calculate_quality_score(
        compilation_success: bool,
        execution_success: bool,
        coverage: CoverageMetrics | None,
        performance: PerformanceMetrics | None,
        stability: StabilityMetrics | None,
    ) -> int:
        """Calculate overall quality score (0-100).

        :param compilation_success: Whether compilation succeeded
        :param execution_success: Whether execution succeeded
        :param coverage: Coverage metrics
        :param performance: Performance metrics
        :param stability: Stability metrics
        :returns: Quality score 0-100
        """
        if not compilation_success:
            return 0

        if not execution_success:
            return 10

        score = 20  # Base score for compiling and running

        # Coverage contribution (0-40 points)
        if coverage:
            if coverage.growth_rate == "excellent":
                score += 40
            elif coverage.growth_rate == "good":
                score += 30
            elif coverage.growth_rate == "poor":
                score += 10

        # Performance contribution (0-25 points)
        if performance:
            if performance.execs_per_sec > 1000:
                score += 25
            elif performance.execs_per_sec > 500:
                score += 20
            elif performance.execs_per_sec > 100:
                score += 10
            elif performance.execs_per_sec > 10:
                score += 5

        # Stability contribution (0-15 points)
        if stability:
            if stability.status == "stable":
                score += 15
            elif stability.status == "unstable":
                score += 10
            elif stability.status == "crashes_frequently":
                score += 5

        return min(score, 100)

    @classmethod
    def generate_quality_assessment(
        cls,
        compilation_result: dict,
        execution_result: dict | None,
        coverage: CoverageMetrics | None,
        performance: PerformanceMetrics | None,
        stability: StabilityMetrics | None,
    ) -> QualityAssessment:
        """Generate complete quality assessment with all feedback.

        :param compilation_result: Compilation results
        :param execution_result: Execution results
        :param coverage: Coverage metrics
        :param performance: Performance metrics
        :param stability: Stability metrics
        :returns: Complete quality assessment
        """
        all_issues = []
        all_strengths = []

        # Analyze each aspect
        comp_issues, comp_strengths = cls.analyze_compilation(compilation_result)
        all_issues.extend(comp_issues)
        all_strengths.extend(comp_strengths)

        if execution_result:
            exec_issues, exec_strengths = cls.analyze_execution(execution_result)
            all_issues.extend(exec_issues)
            all_strengths.extend(exec_strengths)

        if coverage:
            cov_issues, cov_strengths = cls.analyze_coverage(coverage)
            all_issues.extend(cov_issues)
            all_strengths.extend(cov_strengths)

        if performance:
            perf_issues, perf_strengths = cls.analyze_performance(performance)
            all_issues.extend(perf_issues)
            all_strengths.extend(perf_strengths)

        if stability:
            stab_issues, stab_strengths = cls.analyze_stability(stability)
            all_issues.extend(stab_issues)
            all_strengths.extend(stab_strengths)

        # Calculate score
        score = cls.calculate_quality_score(
            compilation_result.get("success", False),
            execution_result.get("success", False) if execution_result else False,
            coverage,
            performance,
            stability,
        )

        # Determine verdict
        if score >= 70:
            verdict = "production-ready"
        elif score >= 30:
            verdict = "needs-improvement"
        else:
            verdict = "broken"

        # Generate recommended actions
        recommended_actions = []
        critical_issues = [i for i in all_issues if i.severity == FeedbackSeverity.CRITICAL]
        warning_issues = [i for i in all_issues if i.severity == FeedbackSeverity.WARNING]

        if critical_issues:
            recommended_actions.append(
                f"Fix {len(critical_issues)} critical issue(s) preventing execution"
            )
        if warning_issues:
            recommended_actions.append(
                f"Address {len(warning_issues)} warning(s) to improve harness quality"
            )
        if verdict == "production-ready":
            recommended_actions.append("Harness is ready for production fuzzing")

        return QualityAssessment(
            score=score,
            verdict=verdict,
            issues=all_issues,
            strengths=all_strengths,
            recommended_actions=recommended_actions,
        )
