"""
Mypy Analyzer Module - Analyzes Python code for type safety issues using Mypy
"""

# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any, List

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding

logger = logging.getLogger(__name__)


class MypyAnalyzer(BaseModule):
    """
    Analyzes Python code for type safety issues using Mypy.

    This module:
    - Runs Mypy type checker on Python files
    - Detects type errors and inconsistencies
    - Reports findings with configurable strictness
    """

    # Map Mypy error codes to severity
    ERROR_SEVERITY_MAP = {
        "error": "medium",
        "note": "info"
    }

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="mypy_analyzer",
            version="1.0.0",
            description="Analyzes Python code for type safety issues using Mypy",
            author="FuzzForge Team",
            category="analyzer",
            tags=["python", "type-checking", "mypy", "sast"],
            input_schema={
                "strict_mode": {
                    "type": "boolean",
                    "description": "Enable strict type checking",
                    "default": False
                },
                "ignore_missing_imports": {
                    "type": "boolean",
                    "description": "Ignore errors about missing imports",
                    "default": True
                },
                "follow_imports": {
                    "type": "string",
                    "enum": ["normal", "silent", "skip", "error"],
                    "description": "How to handle imports",
                    "default": "silent"
                }
            },
            output_schema={
                "findings": {
                    "type": "array",
                    "description": "List of type errors found by Mypy"
                }
            },
            requires_workspace=True
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        follow_imports = config.get("follow_imports", "silent")
        if follow_imports not in ["normal", "silent", "skip", "error"]:
            raise ValueError("follow_imports must be one of: normal, silent, skip, error")

        return True

    async def _run_mypy(
        self,
        workspace: Path,
        strict_mode: bool,
        ignore_missing_imports: bool,
        follow_imports: str
    ) -> str:
        """
        Run Mypy on the workspace.

        Args:
            workspace: Path to workspace
            strict_mode: Enable strict checking
            ignore_missing_imports: Ignore missing import errors
            follow_imports: How to handle imports

        Returns:
            Mypy output as string
        """
        try:
            # Build mypy command
            cmd = [
                "mypy",
                str(workspace),
                "--show-column-numbers",
                "--no-error-summary",
                f"--follow-imports={follow_imports}"
            ]

            if strict_mode:
                cmd.append("--strict")

            if ignore_missing_imports:
                cmd.append("--ignore-missing-imports")

            logger.info(f"Running Mypy on: {workspace}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # Mypy returns non-zero if errors found, which is expected
            output = stdout.decode()
            return output

        except Exception as e:
            logger.error(f"Error running Mypy: {e}")
            return ""

    def _parse_mypy_output(self, output: str, workspace: Path) -> List[ModuleFinding]:
        """
        Parse Mypy output and convert to findings.

        Mypy output format:
        file.py:10:5: error: Incompatible return value type [return-value]
        file.py:15: note: See https://...

        Args:
            output: Mypy stdout
            workspace: Workspace path for relative paths

        Returns:
            List of ModuleFindings
        """
        findings = []

        # Regex to parse mypy output lines
        # Format: filename:line:column: level: message [error-code]
        pattern = r'^(.+?):(\d+)(?::(\d+))?: (error|note): (.+?)(?:\s+\[([^\]]+)\])?$'

        for line in output.splitlines():
            match = re.match(pattern, line.strip())
            if not match:
                continue

            filename, line_num, column, level, message, error_code = match.groups()

            # Convert to relative path
            try:
                file_path = Path(filename)
                rel_path = file_path.relative_to(workspace)
            except (ValueError, TypeError):
                rel_path = Path(filename).name

            # Skip if it's just a note (unless it's a standalone note)
            if level == "note" and not error_code:
                continue

            # Map severity
            severity = self.ERROR_SEVERITY_MAP.get(level, "medium")

            # Create finding
            title = f"Type error: {error_code or 'type-issue'}"
            description = message

            finding = self.create_finding(
                title=title,
                description=description,
                severity=severity,
                category="type-error",
                file_path=str(rel_path),
                line_start=int(line_num),
                line_end=int(line_num),
                recommendation="Review and fix the type inconsistency or add appropriate type annotations",
                metadata={
                    "error_code": error_code or "unknown",
                    "column": int(column) if column else None,
                    "level": level
                }
            )
            findings.append(finding)

        return findings

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute the Mypy analyzer module.

        Args:
            config: Module configuration
            workspace: Path to workspace

        Returns:
            ModuleResult with type checking findings
        """
        start_time = time.time()
        metadata = self.get_metadata()

        # Validate inputs
        self.validate_config(config)
        self.validate_workspace(workspace)

        # Get configuration
        strict_mode = config.get("strict_mode", False)
        ignore_missing_imports = config.get("ignore_missing_imports", True)
        follow_imports = config.get("follow_imports", "silent")

        # Run Mypy
        logger.info("Starting Mypy analysis...")
        mypy_output = await self._run_mypy(
            workspace,
            strict_mode,
            ignore_missing_imports,
            follow_imports
        )

        # Parse output to findings
        findings = self._parse_mypy_output(mypy_output, workspace)

        # Calculate summary
        error_code_counts = {}
        for finding in findings:
            code = finding.metadata.get("error_code", "unknown")
            error_code_counts[code] = error_code_counts.get(code, 0) + 1

        execution_time = time.time() - start_time

        return ModuleResult(
            module=metadata.name,
            version=metadata.version,
            status="success",
            execution_time=execution_time,
            findings=findings,
            summary={
                "total_errors": len(findings),
                "by_error_code": error_code_counts,
                "files_with_errors": len(set(f.file_path for f in findings if f.file_path))
            },
            metadata={
                "strict_mode": strict_mode,
                "ignore_missing_imports": ignore_missing_imports
            }
        )
