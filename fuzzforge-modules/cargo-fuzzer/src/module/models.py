"""Models for the cargo-fuzzer module."""

from pydantic import BaseModel, Field
from fuzzforge_modules_sdk.api.models import FuzzForgeModuleInputBase, FuzzForgeModuleOutputBase

from module.settings import Settings


class FuzzingStats(BaseModel):
    """Statistics from a fuzzing run."""
    
    #: Total number of test case executions
    total_executions: int = 0
    
    #: Executions per second
    executions_per_second: int = 0
    
    #: Number of coverage edges discovered
    coverage_edges: int = 0
    
    #: Size of the corpus
    corpus_size: int = 0
    
    #: Any error message
    error: str = ""


class CrashInfo(BaseModel):
    """Information about a discovered crash."""
    
    #: Path to the crash input file
    file_path: str
    
    #: Hash/name of the crash input
    input_hash: str
    
    #: Size of the crash input in bytes
    input_size: int = 0
    
    #: Crash type (if identified)
    crash_type: str = ""
    
    #: Stack trace (if available)
    stack_trace: str = ""


class TargetResult(BaseModel):
    """Result of fuzzing a single target."""
    
    #: Name of the fuzz target
    target: str
    
    #: List of crashes found
    crashes: list[CrashInfo] = Field(default_factory=list)
    
    #: Fuzzing statistics
    stats: FuzzingStats = Field(default_factory=FuzzingStats)


class Input(FuzzForgeModuleInputBase[Settings]):
    """Input for the cargo-fuzzer module.
    
    Expects:
    - A fuzz project directory with validated harnesses
    - Optionally the source crate to link against
    """


class Output(FuzzForgeModuleOutputBase):
    """Output from the cargo-fuzzer module."""
    
    #: Path to the fuzz project
    fuzz_project: str = ""
    
    #: Number of targets fuzzed
    targets_fuzzed: int = 0
    
    #: Total crashes found across all targets
    total_crashes: int = 0
    
    #: Total executions across all targets
    total_executions: int = 0
    
    #: Path to collected crash files
    crashes_path: str = ""
    
    #: Results per target
    results: list[TargetResult] = Field(default_factory=list)
