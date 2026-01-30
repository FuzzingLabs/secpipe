"""
Gitleaks Secret Detection Module

This module uses Gitleaks to detect secrets and sensitive information in Git repositories
and file systems.
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
from pathlib import Path
from typing import Dict, Any, List
import subprocess
import logging

from ..base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
from . import register_module

logger = logging.getLogger(__name__)


@register_module
class GitleaksModule(BaseModule):
    """Gitleaks secret detection module"""

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="gitleaks",
            version="8.18.0",
            description="Git-specific secret scanning and leak detection using Gitleaks",
            author="FuzzForge Team",
            category="secret_detection",
            tags=["secrets", "git", "leak-detection", "credentials"],
            input_schema={
                "type": "object",
                "properties": {
                    "scan_mode": {
                        "type": "string",
                        "enum": ["detect", "protect"],
                        "default": "detect",
                        "description": "Scan mode: detect (entire repo history) or protect (staged changes)"
                    },
                    "config_file": {
                        "type": "string",
                        "description": "Path to custom Gitleaks configuration file"
                    },
                    "baseline_file": {
                        "type": "string",
                        "description": "Path to baseline file to ignore known findings"
                    },
                    "max_target_megabytes": {
                        "type": "integer",
                        "default": 100,
                        "description": "Maximum size of files to scan (in MB)"
                    },
                    "redact": {
                        "type": "boolean",
                        "default": True,
                        "description": "Redact secrets in output"
                    },
                    "no_git": {
                        "type": "boolean",
                        "default": False,
                        "description": "Scan files without Git context"
                    }
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rule_id": {"type": "string"},
                                "category": {"type": "string"},
                                "file_path": {"type": "string"},
                                "line_number": {"type": "integer"},
                                "secret": {"type": "string"}
                            }
                        }
                    }
                }
            }
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration"""
        scan_mode = config.get("scan_mode", "detect")
        if scan_mode not in ["detect", "protect"]:
            raise ValueError("scan_mode must be 'detect' or 'protect'")

        max_size = config.get("max_target_megabytes", 100)
        if not isinstance(max_size, int) or max_size < 1 or max_size > 1000:
            raise ValueError("max_target_megabytes must be between 1 and 1000")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """Execute Gitleaks secret detection"""
        self.start_timer()

        try:
            # Validate inputs
            self.validate_config(config)
            self.validate_workspace(workspace)

            logger.info(f"Running Gitleaks on {workspace}")

            # Build Gitleaks command
            scan_mode = config.get("scan_mode", "detect")
            cmd = ["gitleaks", scan_mode]

            # Add source path
            cmd.extend(["--source", str(workspace)])

            # Create temp file for JSON output
            import tempfile
            output_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
            output_path = output_file.name
            output_file.close()

            # Add report format and output file
            cmd.extend(["--report-format", "json"])
            cmd.extend(["--report-path", output_path])

            # Add redact option
            if config.get("redact", True):
                cmd.append("--redact")

            # Add max target size
            max_size = config.get("max_target_megabytes", 100)
            cmd.extend(["--max-target-megabytes", str(max_size)])

            # Add config file if specified
            if config.get("config_file"):
                config_path = Path(config["config_file"])
                if config_path.exists():
                    cmd.extend(["--config", str(config_path)])

            # Add baseline file if specified
            if config.get("baseline_file"):
                baseline_path = Path(config["baseline_file"])
                if baseline_path.exists():
                    cmd.extend(["--baseline-path", str(baseline_path)])

            # Add no-git flag if specified
            if config.get("no_git", False):
                cmd.append("--no-git")

            # Add verbose output
            cmd.append("--verbose")

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Run Gitleaks
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace
            )

            stdout, stderr = await process.communicate()

            # Parse results
            findings = []
            try:
                # Read the JSON output from file
                with open(output_path, 'r') as f:
                    output_content = f.read()

                if process.returncode == 0:
                    # No secrets found
                    logger.info("No secrets detected by Gitleaks")
                elif process.returncode == 1:
                    # Secrets found - parse from file content
                    findings = self._parse_gitleaks_output(output_content, workspace)
                else:
                    # Error occurred
                    error_msg = stderr.decode()
                    logger.error(f"Gitleaks failed: {error_msg}")
                    return self.create_result(
                        findings=[],
                        status="failed",
                        error=f"Gitleaks execution failed: {error_msg}"
                    )
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(output_path)
                except:
                    pass

            # Create summary
            summary = {
                "total_leaks": len(findings),
                "unique_rules": len(set(f.metadata.get("rule_id", "") for f in findings)),
                "files_with_leaks": len(set(f.file_path for f in findings if f.file_path)),
                "scan_mode": scan_mode
            }

            logger.info(f"Gitleaks found {len(findings)} potential leaks")

            return self.create_result(
                findings=findings,
                status="success",
                summary=summary
            )

        except Exception as e:
            logger.error(f"Gitleaks module failed: {e}")
            return self.create_result(
                findings=[],
                status="failed",
                error=str(e)
            )

    def _parse_gitleaks_output(self, output: str, workspace: Path) -> List[ModuleFinding]:
        """Parse Gitleaks JSON output into findings"""
        findings = []

        if not output.strip():
            return findings

        try:
            # Gitleaks outputs JSON array
            results = json.loads(output)
            if not isinstance(results, list):
                logger.warning("Unexpected Gitleaks output format")
                return findings

            for result in results:
                # Extract information
                rule_id = result.get("RuleID", "unknown")
                description = result.get("Description", "")
                file_path = result.get("File", "")
                line_number = result.get("StartLine", 0)  # Gitleaks outputs "StartLine", not "LineNumber"
                line_end = result.get("EndLine", 0)
                secret = result.get("Secret", "")
                match_text = result.get("Match", "")

                # Commit info (if available)
                commit = result.get("Commit", "")
                author = result.get("Author", "")
                email = result.get("Email", "")
                date = result.get("Date", "")

                # Make file path relative to workspace
                if file_path:
                    try:
                        rel_path = Path(file_path).relative_to(workspace)
                        file_path = str(rel_path)
                    except ValueError:
                        # If file is outside workspace, keep absolute path
                        pass

                # Determine severity based on rule type
                severity = self._get_leak_severity(rule_id, description)

                # Create finding
                finding = self.create_finding(
                    title=f"Secret leak detected: {rule_id}",
                    description=self._get_leak_description(rule_id, description, commit),
                    severity=severity,
                    category="secret_leak",
                    file_path=file_path if file_path else None,
                    line_start=line_number if line_number > 0 else None,
                    line_end=line_end if line_end > 0 else None,
                    code_snippet=match_text if match_text else secret,
                    recommendation=self._get_leak_recommendation(rule_id),
                    metadata={
                        "rule_id": rule_id,
                        "secret_type": description,
                        "commit": commit,
                        "author": author,
                        "email": email,
                        "date": date,
                        "entropy": result.get("Entropy", 0),
                        "fingerprint": result.get("Fingerprint", "")
                    }
                )

                findings.append(finding)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gitleaks output: {e}")
        except Exception as e:
            logger.warning(f"Error processing Gitleaks results: {e}")

        return findings

    def _get_leak_severity(self, rule_id: str, description: str) -> str:
        """Determine severity based on secret type"""
        critical_patterns = [
            "aws", "amazon", "gcp", "google", "azure", "microsoft",
            "private_key", "rsa", "ssh", "certificate", "database",
            "password", "auth", "token", "secret", "key"
        ]

        rule_lower = rule_id.lower()
        desc_lower = description.lower()

        # Check for critical patterns
        for pattern in critical_patterns:
            if pattern in rule_lower or pattern in desc_lower:
                if any(x in rule_lower for x in ["aws", "gcp", "azure"]):
                    return "critical"
                elif any(x in rule_lower for x in ["private", "key", "password"]):
                    return "high"
                else:
                    return "medium"

        return "low"

    def _get_leak_description(self, rule_id: str, description: str, commit: str) -> str:
        """Get description for the leak finding"""
        base_desc = f"Gitleaks detected a potential secret leak matching rule '{rule_id}'"
        if description:
            base_desc += f" ({description})"

        if commit:
            base_desc += f" in commit {commit[:8]}"

        base_desc += ". This may indicate sensitive information has been committed to version control."

        return base_desc

    def _get_leak_recommendation(self, rule_id: str) -> str:
        """Get remediation recommendation"""
        base_rec = "Remove the secret from the codebase and Git history. "

        if any(pattern in rule_id.lower() for pattern in ["aws", "gcp", "azure"]):
            base_rec += "Revoke the cloud credentials immediately and rotate them. "

        base_rec += "Consider using Git history rewriting tools (git-filter-branch, BFG) " \
                   "to remove sensitive data from commit history. Implement pre-commit hooks " \
                   "to prevent future secret commits."

        return base_rec