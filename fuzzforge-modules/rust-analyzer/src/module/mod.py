"""Rust Analyzer module for FuzzForge.

This module analyzes Rust source code to identify fuzzable entry points,
unsafe blocks, and known vulnerabilities.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from fuzzforge_modules_sdk.api.constants import PATH_TO_OUTPUTS
from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResults
from fuzzforge_modules_sdk.api.modules.base import FuzzForgeModule

from module.models import AnalysisResult, EntryPoint, Input, Output, UnsafeBlock, Vulnerability
from module.settings import Settings

if TYPE_CHECKING:
    from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResource


class Module(FuzzForgeModule):
    """Rust Analyzer module - analyzes Rust code for fuzzable entry points."""

    def __init__(self) -> None:
        """Initialize an instance of the class."""
        name: str = "rust-analyzer"
        version: str = "0.1.0"
        FuzzForgeModule.__init__(self, name=name, version=version)
        self._project_path: Path | None = None
        self._settings: Settings | None = None

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

    def _find_cargo_toml(self, resources: list[FuzzForgeModuleResource]) -> Path | None:
        """Find the Cargo.toml file in the resources.

        :param resources: List of input resources.
        :returns: Path to Cargo.toml or None.

        """
        for resource in resources:
            if resource.path.name == "Cargo.toml":
                return resource.path
            # Check if resource is a directory containing Cargo.toml
            cargo_path = resource.path / "Cargo.toml"
            if cargo_path.exists():
                return cargo_path
        return None

    def _parse_cargo_toml(self, cargo_path: Path) -> tuple[str, str, str]:
        """Parse Cargo.toml to extract crate name, version, and lib name.

        :param cargo_path: Path to Cargo.toml.
        :returns: Tuple of (crate_name, version, lib_name).

        """
        import tomllib

        with cargo_path.open("rb") as f:
            data = tomllib.load(f)

        package = data.get("package", {})
        crate_name = package.get("name", "unknown")
        version = package.get("version", "0.0.0")
        
        # Get lib name - defaults to crate name with dashes converted to underscores
        lib_section = data.get("lib", {})
        lib_name = lib_section.get("name", crate_name.replace("-", "_"))
        
        return crate_name, version, lib_name

    def _find_entry_points(self, project_path: Path) -> list[EntryPoint]:
        """Find fuzzable entry points in the Rust source.

        :param project_path: Path to the Rust project.
        :returns: List of entry points.

        """
        entry_points: list[EntryPoint] = []

        # Patterns for fuzzable functions (take &[u8], &str, or impl Read)
        fuzzable_patterns = [
            r"pub\s+fn\s+(\w+)\s*\([^)]*&\[u8\][^)]*\)",
            r"pub\s+fn\s+(\w+)\s*\([^)]*&str[^)]*\)",
            r"pub\s+fn\s+(\w+)\s*\([^)]*impl\s+Read[^)]*\)",
            r"pub\s+fn\s+(\w+)\s*\([^)]*data:\s*&\[u8\][^)]*\)",
            r"pub\s+fn\s+(\w+)\s*\([^)]*input:\s*&\[u8\][^)]*\)",
            r"pub\s+fn\s+(\w+)\s*\([^)]*buf:\s*&\[u8\][^)]*\)",
        ]

        # Also find parse/decode functions
        parser_patterns = [
            r"pub\s+fn\s+(parse\w*)\s*\([^)]*\)",
            r"pub\s+fn\s+(decode\w*)\s*\([^)]*\)",
            r"pub\s+fn\s+(deserialize\w*)\s*\([^)]*\)",
            r"pub\s+fn\s+(from_bytes\w*)\s*\([^)]*\)",
            r"pub\s+fn\s+(read\w*)\s*\([^)]*\)",
        ]

        src_path = project_path / "src"
        if not src_path.exists():
            src_path = project_path

        for rust_file in src_path.rglob("*.rs"):
            try:
                content = rust_file.read_text()
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    # Check fuzzable patterns
                    for pattern in fuzzable_patterns:
                        match = re.search(pattern, line)
                        if match:
                            entry_points.append(
                                EntryPoint(
                                    function=match.group(1),
                                    file=str(rust_file.relative_to(project_path)),
                                    line=line_num,
                                    signature=line.strip(),
                                    fuzzable=True,
                                )
                            )

                    # Check parser patterns (may need manual review)
                    for pattern in parser_patterns:
                        match = re.search(pattern, line)
                        if match:
                            # Avoid duplicates
                            func_name = match.group(1)
                            if not any(ep.function == func_name for ep in entry_points):
                                entry_points.append(
                                    EntryPoint(
                                        function=func_name,
                                        file=str(rust_file.relative_to(project_path)),
                                        line=line_num,
                                        signature=line.strip(),
                                        fuzzable=True,
                                    )
                                )
            except Exception:
                continue

        return entry_points

    def _find_unsafe_blocks(self, project_path: Path) -> list[UnsafeBlock]:
        """Find unsafe blocks in the Rust source.

        :param project_path: Path to the Rust project.
        :returns: List of unsafe blocks.

        """
        unsafe_blocks: list[UnsafeBlock] = []

        src_path = project_path / "src"
        if not src_path.exists():
            src_path = project_path

        for rust_file in src_path.rglob("*.rs"):
            try:
                content = rust_file.read_text()
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    if "unsafe" in line and ("{" in line or "fn" in line):
                        # Determine context
                        context = "unsafe block"
                        if "unsafe fn" in line:
                            context = "unsafe function"
                        elif "unsafe impl" in line:
                            context = "unsafe impl"
                        elif "*const" in line or "*mut" in line:
                            context = "raw pointer operation"

                        unsafe_blocks.append(
                            UnsafeBlock(
                                file=str(rust_file.relative_to(project_path)),
                                line=line_num,
                                context=context,
                            )
                        )
            except Exception:
                continue

        return unsafe_blocks

    def _run_cargo_audit(self, project_path: Path) -> list[Vulnerability]:
        """Run cargo-audit to find known vulnerabilities.

        :param project_path: Path to the Rust project.
        :returns: List of vulnerabilities.

        """
        vulnerabilities: list[Vulnerability] = []

        try:
            result = subprocess.run(
                ["cargo", "audit", "--json"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.stdout:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data.get("vulnerabilities", {}).get("list", []):
                    advisory = vuln.get("advisory", {})
                    vulnerabilities.append(
                        Vulnerability(
                            advisory_id=advisory.get("id", "UNKNOWN"),
                            crate_name=vuln.get("package", {}).get("name", "unknown"),
                            version=vuln.get("package", {}).get("version", "0.0.0"),
                            title=advisory.get("title", "Unknown vulnerability"),
                            severity=advisory.get("severity", "unknown"),
                        )
                    )
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        return vulnerabilities

    def _run(self, resources: list[FuzzForgeModuleResource]) -> FuzzForgeModuleResults:
        """Run the analysis.

        :param resources: Input resources.
        :returns: Module result status.

        """
        # Find the Rust project
        cargo_path = self._find_cargo_toml(resources)
        if cargo_path is None:
            self.get_logger().error("No Cargo.toml found in resources")
            return FuzzForgeModuleResults.FAILURE

        project_path = cargo_path.parent
        self._project_path = project_path

        self.get_logger().info("Analyzing Rust project", project=str(project_path))

        # Parse Cargo.toml
        crate_name, crate_version, lib_name = self._parse_cargo_toml(cargo_path)
        self.get_logger().info("Found crate", name=crate_name, version=crate_version, lib_name=lib_name)

        # Find entry points
        entry_points = self._find_entry_points(project_path)
        self.get_logger().info("Found entry points", count=len(entry_points))

        # Find unsafe blocks
        unsafe_blocks = self._find_unsafe_blocks(project_path)
        self.get_logger().info("Found unsafe blocks", count=len(unsafe_blocks))

        # Run cargo-audit if enabled
        vulnerabilities: list[Vulnerability] = []
        if self._settings and self._settings.run_audit:
            vulnerabilities = self._run_cargo_audit(project_path)
            self.get_logger().info("Found vulnerabilities", count=len(vulnerabilities))

        # Build result
        analysis = AnalysisResult(
            crate_name=crate_name,
            crate_version=crate_version,
            lib_name=lib_name,
            entry_points=entry_points,
            unsafe_blocks=unsafe_blocks,
            vulnerabilities=vulnerabilities,
            summary={
                "entry_points": len(entry_points),
                "unsafe_blocks": len(unsafe_blocks),
                "vulnerabilities": len(vulnerabilities),
            },
        )

        # Set output data for results.json
        self.set_output(
            analysis=analysis.model_dump(),
        )

        # Write analysis to output file (for backwards compatibility)
        output_path = PATH_TO_OUTPUTS / "analysis.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(analysis.model_dump_json(indent=2))

        self.get_logger().info("Analysis complete", output=str(output_path))

        return FuzzForgeModuleResults.SUCCESS

    def _cleanup(self, settings: Settings) -> None:  # type: ignore[override]
        """Clean up after execution.

        :param settings: Module settings.

        """
        pass
