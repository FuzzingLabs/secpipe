"""
MobSF Scanner Module

Mobile Security Framework (MobSF) integration for comprehensive Android app security analysis.
Performs static analysis on APK files including permissions, manifest analysis, code analysis, and behavior checks.
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

import logging
import os
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List
import aiohttp

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleFinding, ModuleResult

logger = logging.getLogger(__name__)


class MobSFScanner(BaseModule):
    """Mobile Security Framework (MobSF) scanner module for Android applications"""

    SEVERITY_MAP = {
        "dangerous": "critical",
        "high": "high",
        "warning": "medium",
        "medium": "medium",
        "low": "low",
        "info": "low",
        "secure": "low",
    }

    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="mobsf_scanner",
            version="3.9.7",
            description="Comprehensive Android security analysis using Mobile Security Framework (MobSF)",
            author="FuzzForge Team",
            category="android",
            tags=["mobile", "android", "mobsf", "sast", "scanner", "security"],
            input_schema={
                "type": "object",
                "properties": {
                    "mobsf_url": {
                        "type": "string",
                        "description": "MobSF server URL",
                        "default": "http://localhost:8877",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the APK file to scan (absolute or relative to workspace)",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "MobSF API key (if not provided, will try MOBSF_API_KEY env var)",
                        "default": None,
                    },
                    "rescan": {
                        "type": "boolean",
                        "description": "Force rescan even if file was previously analyzed",
                        "default": False,
                    },
                },
                "required": ["file_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "description": "Security findings from MobSF analysis"
                    },
                    "scan_hash": {"type": "string"},
                    "total_findings": {"type": "integer"},
                    "severity_counts": {"type": "object"},
                }
            },
            requires_workspace=True,
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        if "mobsf_url" in config and not isinstance(config["mobsf_url"], str):
            raise ValueError("mobsf_url must be a string")

        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for MobSF scanning")

        return True

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        """
        Execute MobSF security analysis on an APK file.

        Args:
            config: Configuration dict with file_path, mobsf_url, api_key
            workspace: Workspace directory path

        Returns:
            ModuleResult with security findings from MobSF
        """
        self.start_timer()

        try:
            self.validate_config(config)
            self.validate_workspace(workspace)

            # Get configuration
            mobsf_url = config.get("mobsf_url", "http://localhost:8877")
            file_path_str = config["file_path"]
            rescan = config.get("rescan", False)

            # Get API key from config or environment
            api_key = config.get("api_key") or os.environ.get("MOBSF_API_KEY", "")
            if not api_key:
                logger.warning("No MobSF API key provided. Some functionality may be limited.")

            # Resolve APK file path
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = (workspace / file_path).resolve()

            if not file_path.exists():
                raise FileNotFoundError(f"APK file not found: {file_path}")

            if not file_path.is_file():
                raise ValueError(f"APK path must be a file: {file_path}")

            logger.info(f"Starting MobSF scan of APK: {file_path}")

            # Upload and scan APK
            scan_hash = await self._upload_file(mobsf_url, file_path, api_key)
            logger.info(f"APK uploaded to MobSF with hash: {scan_hash}")

            # Start scan
            await self._start_scan(mobsf_url, scan_hash, api_key, rescan=rescan)
            logger.info(f"MobSF scan completed for hash: {scan_hash}")

            # Get JSON results
            scan_results = await self._get_json_results(mobsf_url, scan_hash, api_key)

            # Parse results into findings
            findings = self._parse_scan_results(scan_results, file_path)

            # Create summary
            summary = self._create_summary(findings, scan_hash)

            logger.info(f"✓ MobSF scan completed: {len(findings)} findings")

            return self.create_result(
                findings=findings,
                status="success",
                summary=summary,
                metadata={
                    "tool": "mobsf",
                    "tool_version": "3.9.7",
                    "scan_hash": scan_hash,
                    "apk_file": str(file_path),
                    "mobsf_url": mobsf_url,
                }
            )

        except Exception as exc:
            logger.error(f"MobSF scanner failed: {exc}", exc_info=True)
            return self.create_result(
                findings=[],
                status="failed",
                error=str(exc),
                metadata={"tool": "mobsf", "file_path": config.get("file_path")}
            )

    async def _upload_file(self, mobsf_url: str, file_path: Path, api_key: str) -> str:
        """
        Upload APK file to MobSF server.

        Returns:
            Scan hash for the uploaded file
        """
        headers = {'X-Mobsf-Api-Key': api_key} if api_key else {}

        # Create multipart form data
        filename = file_path.name

        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file',
                             f,
                             filename=filename,
                             content_type='application/vnd.android.package-archive')

                async with session.post(
                    f"{mobsf_url}/api/v1/upload",
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to upload file to MobSF: {error_text}")

                    result = await response.json()
                    scan_hash = result.get('hash')
                    if not scan_hash:
                        raise Exception(f"MobSF upload failed: {result}")

                    return scan_hash

    async def _start_scan(self, mobsf_url: str, scan_hash: str, api_key: str, rescan: bool = False) -> Dict[str, Any]:
        """
        Start MobSF scan for uploaded file.

        Returns:
            Scan result dictionary
        """
        headers = {'X-Mobsf-Api-Key': api_key} if api_key else {}
        data = {
            'hash': scan_hash,
            're_scan': '1' if rescan else '0'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{mobsf_url}/api/v1/scan",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=600)  # 10 minutes for scan
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"MobSF scan failed: {error_text}")

                result = await response.json()
                return result

    async def _get_json_results(self, mobsf_url: str, scan_hash: str, api_key: str) -> Dict[str, Any]:
        """
        Retrieve JSON scan results from MobSF.

        Returns:
            Scan results dictionary
        """
        headers = {'X-Mobsf-Api-Key': api_key} if api_key else {}
        data = {'hash': scan_hash}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{mobsf_url}/api/v1/report_json",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to retrieve MobSF results: {error_text}")

                return await response.json()

    def _parse_scan_results(self, scan_data: Dict[str, Any], apk_path: Path) -> List[ModuleFinding]:
        """Parse MobSF JSON results into standardized findings"""
        findings = []

        # Parse permissions
        if 'permissions' in scan_data:
            for perm_name, perm_attrs in scan_data['permissions'].items():
                if isinstance(perm_attrs, dict):
                    severity = self.SEVERITY_MAP.get(
                        perm_attrs.get('status', '').lower(), 'low'
                    )

                    finding = self.create_finding(
                        title=f"Android Permission: {perm_name}",
                        description=perm_attrs.get('description', 'No description'),
                        severity=severity,
                        category="android-permission",
                        metadata={
                            'permission': perm_name,
                            'status': perm_attrs.get('status'),
                            'info': perm_attrs.get('info'),
                            'tool': 'mobsf',
                        }
                    )
                    findings.append(finding)

        # Parse manifest analysis
        if 'manifest_analysis' in scan_data:
            manifest_findings = scan_data['manifest_analysis'].get('manifest_findings', [])
            for item in manifest_findings:
                if isinstance(item, dict):
                    severity = self.SEVERITY_MAP.get(item.get('severity', '').lower(), 'medium')

                    finding = self.create_finding(
                        title=item.get('title') or item.get('name') or "Manifest Issue",
                        description=item.get('description', 'No description'),
                        severity=severity,
                        category="android-manifest",
                        metadata={
                            'rule': item.get('rule'),
                            'tool': 'mobsf',
                        }
                    )
                    findings.append(finding)

        # Parse code analysis
        if 'code_analysis' in scan_data:
            code_findings = scan_data['code_analysis'].get('findings', {})
            for finding_name, finding_data in code_findings.items():
                if isinstance(finding_data, dict):
                    metadata_dict = finding_data.get('metadata', {})
                    severity = self.SEVERITY_MAP.get(
                        metadata_dict.get('severity', '').lower(), 'medium'
                    )

                    # MobSF returns 'files' as a dict: {filename: line_numbers}
                    files_dict = finding_data.get('files', {})

                    # Create a finding for each affected file
                    if isinstance(files_dict, dict) and files_dict:
                        for file_path, line_numbers in files_dict.items():
                            finding = self.create_finding(
                                title=finding_name,
                                description=metadata_dict.get('description', 'No description'),
                                severity=severity,
                                category="android-code-analysis",
                                file_path=file_path,
                                line_number=line_numbers,  # Can be string like "28" or "65,81"
                                metadata={
                                    'cwe': metadata_dict.get('cwe'),
                                    'owasp': metadata_dict.get('owasp'),
                                    'masvs': metadata_dict.get('masvs'),
                                    'cvss': metadata_dict.get('cvss'),
                                    'ref': metadata_dict.get('ref'),
                                    'line_numbers': line_numbers,
                                    'tool': 'mobsf',
                                }
                            )
                            findings.append(finding)
                    else:
                        # Fallback: create one finding without file info
                        finding = self.create_finding(
                            title=finding_name,
                            description=metadata_dict.get('description', 'No description'),
                            severity=severity,
                            category="android-code-analysis",
                            metadata={
                                'cwe': metadata_dict.get('cwe'),
                                'owasp': metadata_dict.get('owasp'),
                                'masvs': metadata_dict.get('masvs'),
                                'cvss': metadata_dict.get('cvss'),
                                'ref': metadata_dict.get('ref'),
                                'tool': 'mobsf',
                            }
                        )
                        findings.append(finding)

        # Parse behavior analysis
        if 'behaviour' in scan_data:
            for key, value in scan_data['behaviour'].items():
                if isinstance(value, dict):
                    metadata_dict = value.get('metadata', {})
                    labels = metadata_dict.get('label', [])
                    label = labels[0] if labels else 'Unknown Behavior'

                    severity = self.SEVERITY_MAP.get(
                        metadata_dict.get('severity', '').lower(), 'medium'
                    )

                    # MobSF returns 'files' as a dict: {filename: line_numbers}
                    files_dict = value.get('files', {})

                    # Create a finding for each affected file
                    if isinstance(files_dict, dict) and files_dict:
                        for file_path, line_numbers in files_dict.items():
                            finding = self.create_finding(
                                title=f"Behavior: {label}",
                                description=metadata_dict.get('description', 'No description'),
                                severity=severity,
                                category="android-behavior",
                                file_path=file_path,
                                line_number=line_numbers,
                                metadata={
                                    'line_numbers': line_numbers,
                                    'behavior_key': key,
                                    'tool': 'mobsf',
                                }
                            )
                            findings.append(finding)
                    else:
                        # Fallback: create one finding without file info
                        finding = self.create_finding(
                            title=f"Behavior: {label}",
                            description=metadata_dict.get('description', 'No description'),
                            severity=severity,
                            category="android-behavior",
                            metadata={
                                'behavior_key': key,
                                'tool': 'mobsf',
                            }
                        )
                        findings.append(finding)

        logger.debug(f"Parsed {len(findings)} findings from MobSF results")
        return findings

    def _create_summary(self, findings: List[ModuleFinding], scan_hash: str) -> Dict[str, Any]:
        """Create analysis summary"""
        severity_counter = Counter()
        category_counter = Counter()

        for finding in findings:
            severity_counter[finding.severity] += 1
            category_counter[finding.category] += 1

        return {
            "scan_hash": scan_hash,
            "total_findings": len(findings),
            "severity_counts": dict(severity_counter),
            "category_counts": dict(category_counter),
        }
