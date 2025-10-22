"""
Dependency Scanner Module - Scans Python dependencies for known vulnerabilities using pip-audit
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


class DependencyScanner(BaseModule):
    """
    Scans Python dependencies for known vulnerabilities using pip-audit.

    This module:
    - Discovers dependency files (requirements.txt, pyproject.toml, setup.py, Pipfile)
    - Runs pip-audit to check for vulnerable dependencies
    - Reports CVEs with severity and affected versions
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="dependency_scanner",
            version="1.0.0",
            description="Scans Python dependencies for known vulnerabilities",
            author="FuzzForge Team",
            category="scanner",
            tags=["dependencies", "cve", "vulnerabilities", "pip-audit"],
            input_schema={
                "dependency_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of dependency files to scan (auto-discovered if empty)",
                    "default": []
                },
                "ignore_vulns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of vulnerability IDs to ignore",
                    "default": []
                }
            },
            output_schema={
                "findings": {
                    "type": "array",
                    "description": "List of vulnerable dependencies with CVE information"
                }
            },
            requires_workspace=True
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        dep_files = config.get("dependency_files", [])
        if not isinstance(dep_files, list):
            raise ValueError("dependency_files must be a list")

        ignore_vulns = config.get("ignore_vulns", [])
        if not isinstance(ignore_vulns, list):
            raise ValueError("ignore_vulns must be a list")

        return True

    def _discover_dependency_files(self, workspace: Path) -> List[Path]:
        """
        Discover Python dependency files in workspace.

        Returns:
            List of discovered dependency file paths
        """
        dependency_patterns = [
            "requirements.txt",
            "*requirements*.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock"
        ]

        found_files = []
        for pattern in dependency_patterns:
            found_files.extend(workspace.rglob(pattern))

        # Deduplicate and return
        unique_files = list(set(found_files))
        logger.info(f"Discovered {len(unique_files)} dependency files")
        return unique_files

    async def _run_pip_audit(self, file_path: Path) -> Dict[str, Any]:
        """
        Run pip-audit on a specific dependency file.

        Args:
            file_path: Path to dependency file

        Returns:
            pip-audit JSON output as dict
        """
        try:
            # Run pip-audit with JSON output
            cmd = [
                "pip-audit",
                "--requirement", str(file_path),
                "--format", "json",
                "--progress-spinner", "off"
            ]

            logger.info(f"Running pip-audit on: {file_path.name}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # pip-audit returns 0 if no vulns, 1 if vulns found
            if process.returncode not in [0, 1]:
                logger.error(f"pip-audit failed: {stderr.decode()}")
                return {"dependencies": []}

            # Parse JSON output
            result = json.loads(stdout.decode())
            return result

        except Exception as e:
            logger.error(f"Error running pip-audit on {file_path}: {e}")
            return {"dependencies": []}

    def _convert_to_findings(
        self,
        audit_result: Dict[str, Any],
        file_path: Path,
        workspace: Path,
        ignore_vulns: List[str]
    ) -> List[ModuleFinding]:
        """
        Convert pip-audit results to ModuleFindings.

        Args:
            audit_result: pip-audit JSON output
            file_path: Path to scanned file
            workspace: Workspace path for relative path calculation
            ignore_vulns: List of vulnerability IDs to ignore

        Returns:
            List of ModuleFindings
        """
        findings = []

        # pip-audit format: {"dependencies": [{package, version, vulns: []}]}
        for dep in audit_result.get("dependencies", []):
            package_name = dep.get("name", "unknown")
            package_version = dep.get("version", "unknown")
            vulnerabilities = dep.get("vulns", [])

            for vuln in vulnerabilities:
                vuln_id = vuln.get("id", "UNKNOWN")

                # Skip if in ignore list
                if vuln_id in ignore_vulns:
                    logger.debug(f"Ignoring vulnerability: {vuln_id}")
                    continue

                description = vuln.get("description", "No description available")
                fix_versions = vuln.get("fix_versions", [])

                # Map CVSS scores to severity
                # pip-audit doesn't always provide CVSS, so we default to medium
                severity = "medium"

                # Try to get relative path
                try:
                    rel_path = file_path.relative_to(workspace)
                except ValueError:
                    rel_path = file_path

                recommendation = f"Upgrade {package_name} to a fixed version: {', '.join(fix_versions)}" if fix_versions else f"Check for updates to {package_name}"

                finding = self.create_finding(
                    title=f"Vulnerable dependency: {package_name} ({vuln_id})",
                    description=f"{description}\n\nAffected package: {package_name} {package_version}",
                    severity=severity,
                    category="vulnerable-dependency",
                    file_path=str(rel_path),
                    recommendation=recommendation,
                    metadata={
                        "cve_id": vuln_id,
                        "package": package_name,
                        "installed_version": package_version,
                        "fix_versions": fix_versions,
                        "aliases": vuln.get("aliases", []),
                        "link": vuln.get("link", "")
                    }
                )
                findings.append(finding)

        return findings

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute the dependency scanning module.

        Args:
            config: Module configuration
            workspace: Path to workspace

        Returns:
            ModuleResult with vulnerability findings
        """
        start_time = time.time()
        metadata = self.get_metadata()

        # Validate inputs
        self.validate_config(config)
        self.validate_workspace(workspace)

        # Get configuration
        specified_files = config.get("dependency_files", [])
        ignore_vulns = config.get("ignore_vulns", [])

        # Discover or use specified dependency files
        if specified_files:
            dep_files = [workspace / f for f in specified_files]
        else:
            dep_files = self._discover_dependency_files(workspace)

        if not dep_files:
            logger.warning("No dependency files found in workspace")
            return ModuleResult(
                module=metadata.name,
                version=metadata.version,
                status="success",
                execution_time=time.time() - start_time,
                findings=[],
                summary={
                    "total_files": 0,
                    "total_vulnerabilities": 0,
                    "vulnerable_packages": 0
                }
            )

        # Scan each dependency file
        all_findings = []
        files_scanned = 0

        for dep_file in dep_files:
            if not dep_file.exists():
                logger.warning(f"Dependency file not found: {dep_file}")
                continue

            logger.info(f"Scanning dependencies in: {dep_file.name}")
            audit_result = await self._run_pip_audit(dep_file)
            findings = self._convert_to_findings(audit_result, dep_file, workspace, ignore_vulns)

            all_findings.extend(findings)
            files_scanned += 1

        # Calculate summary
        unique_packages = len(set(f.metadata.get("package") for f in all_findings))

        execution_time = time.time() - start_time

        return ModuleResult(
            module=metadata.name,
            version=metadata.version,
            status="success",
            execution_time=execution_time,
            findings=all_findings,
            summary={
                "total_files": files_scanned,
                "total_vulnerabilities": len(all_findings),
                "vulnerable_packages": unique_packages
            },
            metadata={
                "scanned_files": [str(f.name) for f in dep_files if f.exists()]
            }
        )
