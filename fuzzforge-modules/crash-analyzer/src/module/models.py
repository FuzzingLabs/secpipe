"""Models for the crash-analyzer module."""

from enum import Enum

from pydantic import BaseModel, Field
from fuzzforge_modules_sdk.api.models import FuzzForgeModuleInputBase, FuzzForgeModuleOutputBase

from module.settings import Settings


class Severity(str, Enum):
    """Severity level of a crash."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CrashAnalysis(BaseModel):
    """Analysis of a single crash."""
    
    #: Name of the fuzz target
    target: str
    
    #: Path to the input file that caused the crash
    input_file: str
    
    #: Hash of the input for identification
    input_hash: str
    
    #: Size of the input in bytes
    input_size: int = 0
    
    #: Type of crash (e.g., "heap-buffer-overflow", "panic")
    crash_type: str = "unknown"
    
    #: Severity level
    severity: Severity = Severity.UNKNOWN
    
    #: Stack trace from reproducing the crash
    stack_trace: str = ""
    
    #: Whether this crash is a duplicate of another
    is_duplicate: bool = False
    
    #: Signature for deduplication
    signature: str = ""


class Input(FuzzForgeModuleInputBase[Settings]):
    """Input for the crash-analyzer module.
    
    Expects:
    - Crashes directory from cargo-fuzzer
    - Optionally the fuzz project for reproduction
    """


class Output(FuzzForgeModuleOutputBase):
    """Output from the crash-analyzer module."""
    
    #: Total number of crashes analyzed
    total_crashes: int = 0
    
    #: Number of unique crashes (after deduplication)
    unique_crashes: int = 0
    
    #: Number of duplicate crashes
    duplicate_crashes: int = 0
    
    #: Summary by severity
    severity_summary: dict[str, int] = Field(default_factory=dict)
    
    #: Unique crash analyses
    unique_analyses: list[CrashAnalysis] = Field(default_factory=list)
    
    #: Duplicate crash analyses
    duplicate_analyses: list[CrashAnalysis] = Field(default_factory=list)
