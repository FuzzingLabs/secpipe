"""Models for rust-analyzer module."""

from pathlib import Path

from pydantic import BaseModel

from fuzzforge_modules_sdk.api.models import FuzzForgeModuleInputBase, FuzzForgeModuleOutputBase

from module.settings import Settings


class Input(FuzzForgeModuleInputBase[Settings]):
    """Input for the rust-analyzer module."""


class EntryPoint(BaseModel):
    """A fuzzable entry point in the Rust codebase."""

    #: Function name.
    function: str

    #: Source file path.
    file: str

    #: Line number.
    line: int

    #: Function signature.
    signature: str

    #: Whether the function takes &[u8] or similar fuzzable input.
    fuzzable: bool = True


class UnsafeBlock(BaseModel):
    """An unsafe block detected in the codebase."""

    #: Source file path.
    file: str

    #: Line number.
    line: int

    #: Context description.
    context: str


class Vulnerability(BaseModel):
    """A known vulnerability from cargo-audit."""

    #: Advisory ID (e.g., RUSTSEC-2021-0001).
    advisory_id: str

    #: Affected crate name.
    crate_name: str

    #: Affected version.
    version: str

    #: Vulnerability title.
    title: str

    #: Severity level.
    severity: str


class AnalysisResult(BaseModel):
    """The complete analysis result."""

    #: Crate name from Cargo.toml (use this in fuzz/Cargo.toml dependencies).
    crate_name: str

    #: Crate version.
    crate_version: str
    
    #: Library name for use in Rust code (use in `use` statements).
    #: In Rust, dashes become underscores: "fuzz-demo" -> "fuzz_demo".
    lib_name: str = ""

    #: List of fuzzable entry points.
    entry_points: list[EntryPoint]

    #: List of unsafe blocks.
    unsafe_blocks: list[UnsafeBlock]

    #: List of known vulnerabilities.
    vulnerabilities: list[Vulnerability]

    #: Summary statistics.
    summary: dict[str, int]


class Output(FuzzForgeModuleOutputBase):
    """Output for the rust-analyzer module."""

    #: The analysis result (as dict for serialization).
    analysis: dict | None = None

    #: Path to the analysis JSON file.
    analysis_file: Path | None = None
