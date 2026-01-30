"""
Category-specific benchmark configurations

Defines expected metrics and performance thresholds for each module category.
"""

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum


class ModuleCategory(str, Enum):
    """Module categories for benchmarking"""
    FUZZER = "fuzzer"
    SCANNER = "scanner"
    ANALYZER = "analyzer"
    SECRET_DETECTION = "secret_detection"
    REPORTER = "reporter"


@dataclass
class CategoryBenchmarkConfig:
    """Benchmark configuration for a module category"""
    category: ModuleCategory
    expected_metrics: List[str]
    performance_thresholds: Dict[str, float]
    description: str


# Fuzzer category configuration
FUZZER_CONFIG = CategoryBenchmarkConfig(
    category=ModuleCategory.FUZZER,
    expected_metrics=[
        "execs_per_sec",
        "coverage_rate",
        "time_to_first_crash",
        "corpus_efficiency",
        "execution_time",
        "peak_memory_mb"
    ],
    performance_thresholds={
        "min_execs_per_sec": 1000,  # Minimum executions per second
        "max_execution_time_small": 10.0,  # Max time for small project (seconds)
        "max_execution_time_medium": 60.0,  # Max time for medium project
        "max_memory_mb": 2048,  # Maximum memory usage
        "min_coverage_rate": 1.0,  # Minimum new coverage per second
    },
    description="Fuzzing modules: coverage-guided fuzz testing"
)

# Scanner category configuration
SCANNER_CONFIG = CategoryBenchmarkConfig(
    category=ModuleCategory.SCANNER,
    expected_metrics=[
        "files_per_sec",
        "loc_per_sec",
        "execution_time",
        "peak_memory_mb",
        "findings_count"
    ],
    performance_thresholds={
        "min_files_per_sec": 100,  # Minimum files scanned per second
        "min_loc_per_sec": 10000,  # Minimum lines of code per second
        "max_execution_time_small": 1.0,
        "max_execution_time_medium": 10.0,
        "max_memory_mb": 512,
    },
    description="File scanning modules: fast pattern-based scanning"
)

# Secret detection category configuration
SECRET_DETECTION_CONFIG = CategoryBenchmarkConfig(
    category=ModuleCategory.SECRET_DETECTION,
    expected_metrics=[
        "patterns_per_sec",
        "precision",
        "recall",
        "f1_score",
        "false_positive_rate",
        "execution_time",
        "peak_memory_mb"
    ],
    performance_thresholds={
        "min_patterns_per_sec": 1000,
        "min_precision": 0.90,  # 90% precision target
        "min_recall": 0.95,  # 95% recall target
        "max_false_positives": 5,  # Max false positives per 100 secrets
        "max_execution_time_small": 2.0,
        "max_execution_time_medium": 20.0,
        "max_memory_mb": 1024,
    },
    description="Secret detection modules: high precision pattern matching"
)

# Analyzer category configuration
ANALYZER_CONFIG = CategoryBenchmarkConfig(
    category=ModuleCategory.ANALYZER,
    expected_metrics=[
        "analysis_depth",
        "files_analyzed_per_sec",
        "execution_time",
        "peak_memory_mb",
        "findings_count",
        "accuracy"
    ],
    performance_thresholds={
        "min_files_per_sec": 10,  # Slower than scanners due to deep analysis
        "max_execution_time_small": 5.0,
        "max_execution_time_medium": 60.0,
        "max_memory_mb": 2048,
        "min_accuracy": 0.85,  # 85% accuracy target
    },
    description="Code analysis modules: deep semantic analysis"
)

# Reporter category configuration
REPORTER_CONFIG = CategoryBenchmarkConfig(
    category=ModuleCategory.REPORTER,
    expected_metrics=[
        "report_generation_time",
        "findings_per_sec",
        "peak_memory_mb"
    ],
    performance_thresholds={
        "max_report_time_100_findings": 1.0,  # Max 1 second for 100 findings
        "max_report_time_1000_findings": 10.0,  # Max 10 seconds for 1000 findings
        "max_memory_mb": 256,
    },
    description="Reporting modules: fast report generation"
)


# Category configurations map
CATEGORY_CONFIGS = {
    ModuleCategory.FUZZER: FUZZER_CONFIG,
    ModuleCategory.SCANNER: SCANNER_CONFIG,
    ModuleCategory.SECRET_DETECTION: SECRET_DETECTION_CONFIG,
    ModuleCategory.ANALYZER: ANALYZER_CONFIG,
    ModuleCategory.REPORTER: REPORTER_CONFIG,
}


def get_category_config(category: ModuleCategory) -> CategoryBenchmarkConfig:
    """Get benchmark configuration for a category"""
    return CATEGORY_CONFIGS[category]


def get_threshold(category: ModuleCategory, metric: str) -> float:
    """Get performance threshold for a specific metric"""
    config = get_category_config(category)
    return config.performance_thresholds.get(metric, 0.0)
