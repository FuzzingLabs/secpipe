"""Feedback types and schemas for harness testing."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FeedbackSeverity(str, Enum):
    """Severity levels for feedback issues."""

    CRITICAL = "critical"  # Blocks execution (compilation errors, crashes)
    WARNING = "warning"  # Should fix (low coverage, slow execution)
    INFO = "info"  # Nice to have (optimization suggestions)


class FeedbackCategory(str, Enum):
    """Categories of feedback."""

    COMPILATION = "compilation"
    EXECUTION = "execution"
    PERFORMANCE = "performance"
    COVERAGE = "coverage"
    STABILITY = "stability"
    CODE_QUALITY = "code_quality"


class FeedbackIssue(BaseModel):
    """A single feedback issue with actionable suggestion."""

    category: FeedbackCategory
    severity: FeedbackSeverity
    type: str = Field(description="Specific issue type (e.g., 'low_coverage', 'compilation_error')")
    message: str = Field(description="Human-readable description of the issue")
    suggestion: str = Field(description="Actionable suggestion for AI agent to fix the issue")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional technical details")


class CompilationResult(BaseModel):
    """Results from compilation attempt."""

    success: bool
    time_ms: int | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stderr: str | None = None


class ExecutionResult(BaseModel):
    """Results from execution test."""

    success: bool
    runs_completed: int | None = None
    immediate_crash: bool = False
    timeout: bool = False
    crash_details: str | None = None


class CoverageMetrics(BaseModel):
    """Coverage metrics from fuzzing trial."""

    initial_edges: int = 0
    final_edges: int = 0
    new_edges_found: int = 0
    growth_rate: str = Field(
        description="Qualitative assessment: 'excellent', 'good', 'poor', 'none'"
    )
    percentage_estimate: float | None = Field(
        None, description="Estimated percentage of target code covered"
    )
    stagnation_time_sec: float | None = Field(
        None, description="Time until coverage stopped growing"
    )


class PerformanceMetrics(BaseModel):
    """Performance metrics from fuzzing trial."""

    total_execs: int
    execs_per_sec: float
    average_exec_time_us: float | None = None
    performance_rating: str = Field(
        description="'excellent' (>1000/s), 'good' (100-1000/s), 'poor' (<100/s)"
    )


class StabilityMetrics(BaseModel):
    """Stability metrics from fuzzing trial."""

    status: str = Field(
        description="'stable', 'unstable', 'crashes_frequently', 'hangs'"
    )
    crashes_found: int = 0
    hangs_found: int = 0
    unique_crashes: int = 0
    crash_rate: float = Field(0.0, description="Crashes per 1000 executions")


class FuzzingTrial(BaseModel):
    """Results from short fuzzing trial."""

    duration_seconds: int
    coverage: CoverageMetrics
    performance: PerformanceMetrics
    stability: StabilityMetrics
    trial_successful: bool


class QualityAssessment(BaseModel):
    """Overall quality assessment of the harness."""

    score: int = Field(ge=0, le=100, description="Quality score 0-100")
    verdict: str = Field(
        description="'production-ready', 'needs-improvement', 'broken'"
    )
    issues: list[FeedbackIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class HarnessEvaluation(BaseModel):
    """Complete evaluation of a single harness."""

    name: str
    path: str | None = None
    compilation: CompilationResult
    execution: ExecutionResult | None = None
    fuzzing_trial: FuzzingTrial | None = None
    quality: QualityAssessment


class EvaluationSummary(BaseModel):
    """Summary of all harness evaluations."""

    total_harnesses: int
    production_ready: int
    needs_improvement: int
    broken: int
    average_score: float
    recommended_action: str


class HarnessTestReport(BaseModel):
    """Complete harness testing report."""

    harnesses: list[HarnessEvaluation]
    summary: EvaluationSummary
    test_configuration: dict[str, Any] = Field(default_factory=dict)
