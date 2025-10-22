"""
Bandit Analyzer Module - Analyzes Python code for security issues using Bandit
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
import json
import logging
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


class BanditAnalyzer(BaseModule):
    """
    Analyzes Python code for security issues using Bandit.

    This module:
    - Runs Bandit security linter on Python files
    - Detects common security issues (SQL injection, hardcoded secrets, etc.)
    - Reports findings with severity levels
    """

    # Severity mapping from Bandit levels to our standard
    SEVERITY_MAP = {
        "LOW": "low",
        "MEDIUM": "medium",
        "HIGH": "high"
    }

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="bandit_analyzer",
            version="1.0.0",
            description="Analyzes Python code for security issues using Bandit",
            author="FuzzForge Team",
            category="analyzer",
            tags=["python", "security", "bandit", "sast"],
            input_schema={
                "severity_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Minimum severity level to report",
                    "default": "low"
                },
                "confidence_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Minimum confidence level to report",
                    "default": "medium"
                },
                "exclude_tests": {
                    "type": "boolean",
                    "description": "Exclude test files from analysis",
                    "default": True
                },
                "skip_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Bandit test IDs to skip",
                    "default": []
                }
            },
            output_schema={
                "findings": {
                    "type": "array",
                    "description": "List of security issues found by Bandit"
                }
            },
            requires_workspace=True
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        severity = config.get("severity_level", "low")
        if severity not in ["low", "medium", "high"]:
            raise ValueError("severity_level must be one of: low, medium, high")

        confidence = config.get("confidence_level", "medium")
        if confidence not in ["low", "medium", "high"]:
            raise ValueError("confidence_level must be one of: low, medium, high")

        skip_ids = config.get("skip_ids", [])
        if not isinstance(skip_ids, list):
            raise ValueError("skip_ids must be a list")

        return True

    async def _run_bandit(
        self,
        workspace: Path,
        severity_level: str,
        confidence_level: str,
        exclude_tests: bool,
        skip_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Run Bandit on the workspace.

        Args:
            workspace: Path to workspace
            severity_level: Minimum severity to report
            confidence_level: Minimum confidence to report
            exclude_tests: Whether to exclude test files
            skip_ids: List of test IDs to skip

        Returns:
            Bandit JSON output as dict
        """
        try:
            # Build bandit command
            cmd = [
                "bandit",
                "-r", str(workspace),
                "-f", "json",
                "-ll",  # Report all findings (we'll filter later)
            ]

            # Add exclude patterns for test files
            if exclude_tests:
                cmd.extend(["-x", "*/test_*.py,*/tests/*,*_test.py"])

            # Add skip IDs if specified
            if skip_ids:
                cmd.extend(["-s", ",".join(skip_ids)])

            logger.info(f"Running Bandit on: {workspace}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # Bandit returns non-zero if issues found, which is expected
            if process.returncode not in [0, 1]:
                logger.error(f"Bandit failed: {stderr.decode()}")
                return {"results": []}

            # Parse JSON output
            result = json.loads(stdout.decode())
            return result

        except Exception as e:
            logger.error(f"Error running Bandit: {e}")
            return {"results": []}

    def _should_include_finding(
        self,
        issue: Dict[str, Any],
        min_severity: str,
        min_confidence: str
    ) -> bool:
        """
        Determine if a Bandit issue should be included based on severity/confidence.

        Args:
            issue: Bandit issue dict
            min_severity: Minimum severity threshold
            min_confidence: Minimum confidence threshold

        Returns:
            True if issue should be included
        """
        severity_order = ["low", "medium", "high"]
        issue_severity = issue.get("issue_severity", "LOW").lower()
        issue_confidence = issue.get("issue_confidence", "LOW").lower()

        severity_meets_threshold = severity_order.index(issue_severity) >= severity_order.index(min_severity)
        confidence_meets_threshold = severity_order.index(issue_confidence) >= severity_order.index(min_confidence)

        return severity_meets_threshold and confidence_meets_threshold

    def _convert_to_findings(
        self,
        bandit_result: Dict[str, Any],
        workspace: Path,
        min_severity: str,
        min_confidence: str
    ) -> List[ModuleFinding]:
        """
        Convert Bandit results to ModuleFindings.

        Args:
            bandit_result: Bandit JSON output
            workspace: Workspace path for relative paths
            min_severity: Minimum severity to include
            min_confidence: Minimum confidence to include

        Returns:
            List of ModuleFindings
        """
        findings = []

        for issue in bandit_result.get("results", []):
            # Filter by severity and confidence
            if not self._should_include_finding(issue, min_severity, min_confidence):
                continue

            # Extract issue details
            test_id = issue.get("test_id", "B000")
            test_name = issue.get("test_name", "unknown")
            issue_text = issue.get("issue_text", "No description")
            severity = self.SEVERITY_MAP.get(issue.get("issue_severity", "LOW"), "low")

            # File location
            filename = issue.get("filename", "")
            line_number = issue.get("line_number", 0)
            code = issue.get("code", "")

            # Try to get relative path
            try:
                file_path = Path(filename)
                rel_path = file_path.relative_to(workspace)
            except (ValueError, TypeError):
                rel_path = Path(filename).name

            # Create finding
            finding = self.create_finding(
                title=f"{test_name} ({test_id})",
                description=issue_text,
                severity=severity,
                category="security-issue",
                file_path=str(rel_path),
                line_start=line_number,
                line_end=line_number,
                code_snippet=code.strip() if code else None,
                recommendation=f"Review and fix the security issue identified by Bandit test {test_id}",
                metadata={
                    "test_id": test_id,
                    "test_name": test_name,
                    "confidence": issue.get("issue_confidence", "LOW").lower(),
                    "cwe": issue.get("issue_cwe", {}).get("id") if issue.get("issue_cwe") else None,
                    "more_info": issue.get("more_info", "")
                }
            )
            findings.append(finding)

        return findings

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute the Bandit analyzer module.

        Args:
            config: Module configuration
            workspace: Path to workspace

        Returns:
            ModuleResult with security findings
        """
        start_time = time.time()
        metadata = self.get_metadata()

        # Validate inputs
        self.validate_config(config)
        self.validate_workspace(workspace)

        # Get configuration
        severity_level = config.get("severity_level", "low")
        confidence_level = config.get("confidence_level", "medium")
        exclude_tests = config.get("exclude_tests", True)
        skip_ids = config.get("skip_ids", [])

        # Run Bandit
        logger.info("Starting Bandit analysis...")
        bandit_result = await self._run_bandit(
            workspace,
            severity_level,
            confidence_level,
            exclude_tests,
            skip_ids
        )

        # Convert to findings
        findings = self._convert_to_findings(
            bandit_result,
            workspace,
            severity_level,
            confidence_level
        )

        # Calculate summary
        severity_counts = {}
        for finding in findings:
            sev = finding.severity
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        execution_time = time.time() - start_time

        return ModuleResult(
            module=metadata.name,
            version=metadata.version,
            status="success",
            execution_time=execution_time,
            findings=findings,
            summary={
                "total_issues": len(findings),
                "by_severity": severity_counts,
                "files_analyzed": len(set(f.file_path for f in findings if f.file_path))
            },
            metadata={
                "bandit_version": bandit_result.get("generated_at", "unknown"),
                "metrics": bandit_result.get("metrics", {})
            }
        )
