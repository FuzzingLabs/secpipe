"""
TruffleHog Secret Detection Module

This module uses TruffleHog to detect secrets, credentials, and sensitive information
with verification capabilities.
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
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import subprocess
import logging

from ..base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
from . import register_module

logger = logging.getLogger(__name__)


@register_module
class TruffleHogModule(BaseModule):
    """TruffleHog secret detection module"""

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="trufflehog",
            version="3.63.2",
            description="Comprehensive secret detection with verification using TruffleHog",
            author="FuzzForge Team",
            category="secret_detection",
            tags=["secrets", "credentials", "sensitive-data", "verification"],
            input_schema={
                "type": "object",
                "properties": {
                    "verify": {
                        "type": "boolean",
                        "default": False,
                        "description": "Verify discovered secrets"
                    },
                    "include_detectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific detectors to include"
                    },
                    "exclude_detectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific detectors to exclude"
                    },
                    "concurrency": {
                        "type": "integer",
                        "default": 10,
                        "description": "Number of concurrent workers"
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
                                "detector": {"type": "string"},
                                "verified": {"type": "boolean"},
                                "file_path": {"type": "string"},
                                "line": {"type": "integer"},
                                "secret": {"type": "string"}
                            }
                        }
                    }
                }
            }
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration"""
        # Check concurrency bounds
        concurrency = config.get("concurrency", 10)
        if not isinstance(concurrency, int) or concurrency < 1 or concurrency > 50:
            raise ValueError("Concurrency must be between 1 and 50")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """Execute TruffleHog secret detection"""
        self.start_timer()

        try:
            # Validate inputs
            self.validate_config(config)
            self.validate_workspace(workspace)

            logger.info(f"Running TruffleHog on {workspace}")

            # Build TruffleHog command
            cmd = ["trufflehog", "filesystem", str(workspace)]

            # Add verification flag
            if config.get("verify", False):
                cmd.append("--verify")
            else:
                # Explicitly disable verification to get all unverified secrets
                cmd.append("--no-verification")

            # Add JSON output
            cmd.extend(["--json", "--no-update"])

            # Add concurrency
            cmd.extend(["--concurrency", str(config.get("concurrency", 10))])

            # Add include/exclude detectors
            if config.get("include_detectors"):
                cmd.extend(["--include-detectors", ",".join(config["include_detectors"])])

            if config.get("exclude_detectors"):
                cmd.extend(["--exclude-detectors", ",".join(config["exclude_detectors"])])

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Run TruffleHog
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace
            )

            stdout, stderr = await process.communicate()

            # Parse results
            findings = []
            if process.returncode == 0 or process.returncode == 1:  # 1 indicates secrets found
                findings = self._parse_trufflehog_output(stdout.decode(), workspace)
            else:
                error_msg = stderr.decode()
                logger.error(f"TruffleHog failed: {error_msg}")
                return self.create_result(
                    findings=[],
                    status="failed",
                    error=f"TruffleHog execution failed: {error_msg}"
                )

            # Create summary
            summary = {
                "total_secrets": len(findings),
                "verified_secrets": len([f for f in findings if f.metadata.get("verified", False)]),
                "detectors_triggered": len(set(f.metadata.get("detector", "") for f in findings)),
                "files_with_secrets": len(set(f.file_path for f in findings if f.file_path))
            }

            logger.info(f"TruffleHog found {len(findings)} secrets")

            return self.create_result(
                findings=findings,
                status="success",
                summary=summary
            )

        except Exception as e:
            logger.error(f"TruffleHog module failed: {e}")
            return self.create_result(
                findings=[],
                status="failed",
                error=str(e)
            )

    def _parse_trufflehog_output(self, output: str, workspace: Path) -> List[ModuleFinding]:
        """Parse TruffleHog JSON output into findings"""
        findings = []

        for line in output.strip().split('\n'):
            if not line.strip():
                continue

            try:
                result = json.loads(line)

                # Extract information
                detector = result.get("DetectorName", "unknown")
                verified = result.get("Verified", False)
                raw_secret = result.get("Raw", "")

                # Source info
                source_metadata = result.get("SourceMetadata", {})
                source_data = source_metadata.get("Data", {})
                file_path = source_data.get("Filesystem", {}).get("file", "")
                line_num = source_data.get("Filesystem", {}).get("line", 0)

                # Make file path relative to workspace
                if file_path:
                    try:
                        rel_path = Path(file_path).relative_to(workspace)
                        file_path = str(rel_path)
                    except ValueError:
                        # If file is outside workspace, keep absolute path
                        pass

                # Determine severity based on verification and detector type
                severity = self._get_secret_severity(detector, verified, raw_secret)

                # Create finding
                finding = self.create_finding(
                    title=f"{detector} secret detected",
                    description=self._get_secret_description(detector, verified),
                    severity=severity,
                    category="secret_detection",
                    file_path=file_path if file_path else None,
                    line_start=line_num if line_num > 0 else None,
                    code_snippet=self._truncate_secret(raw_secret),
                    recommendation=self._get_secret_recommendation(detector, verified),
                    metadata={
                        "detector": detector,
                        "verified": verified,
                        "detector_type": result.get("DetectorType", ""),
                        "decoder_type": result.get("DecoderType", ""),
                        "structured_data": result.get("StructuredData", {})
                    }
                )

                findings.append(finding)

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse TruffleHog output line: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error processing TruffleHog result: {e}")
                continue

        return findings

    def _get_secret_severity(self, detector: str, verified: bool, secret: str) -> str:
        """Determine severity based on secret type and verification status"""
        if verified:
            # Verified secrets are always high risk
            critical_detectors = ["aws", "gcp", "azure", "github", "gitlab", "database"]
            if any(crit in detector.lower() for crit in critical_detectors):
                return "critical"
            return "high"

        # Unverified secrets
        high_risk_detectors = ["private_key", "certificate", "password", "token"]
        if any(high in detector.lower() for high in high_risk_detectors):
            return "medium"

        return "low"

    def _get_secret_description(self, detector: str, verified: bool) -> str:
        """Get description for the secret finding"""
        verification_status = "verified and active" if verified else "unverified"
        return f"A {detector} secret was detected and is {verification_status}. " \
               f"This may represent a security risk if the credential is valid."

    def _get_secret_recommendation(self, detector: str, verified: bool) -> str:
        """Get remediation recommendation"""
        if verified:
            return f"IMMEDIATE ACTION REQUIRED: This {detector} secret is verified and active. " \
                   f"Revoke the credential immediately, remove it from the codebase, and " \
                   f"implement proper secret management practices."
        else:
            return f"Review this {detector} secret to determine if it's valid. " \
                   f"If real, revoke the credential and remove it from the codebase. " \
                   f"Consider implementing secret scanning in CI/CD pipelines."

    def _truncate_secret(self, secret: str, max_length: int = 50) -> str:
        """Truncate secret for display purposes"""
        if len(secret) <= max_length:
            return secret
        return secret[:max_length] + "..."