"""
Native Reporter Module - Generates native FuzzForge format security reports
(Previously SARIF Reporter - now generates native format, SARIF export available separately)
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
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

try:
    from toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding
except ImportError:
    try:
        from modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding
    except ImportError:
        from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult, ModuleFinding

logger = logging.getLogger(__name__)


class SARIFReporter(BaseModule):
    """
    Generates native FuzzForge format security reports.

    This module:
    - Converts findings to native FuzzForge format
    - Aggregates results from multiple modules
    - Adds metadata and context
    - Provides actionable recommendations
    - (SARIF export available via separate exporter module)
    """

    def get_metadata(self) -> ModuleMetadata:
        """Get module metadata"""
        return ModuleMetadata(
            name="native_reporter",
            version="2.0.0",
            description="Generates native FuzzForge format security reports",
            author="FuzzForge Team",
            category="reporter",
            tags=["reporting", "native", "output"],
            input_schema={
                "findings": {
                    "type": "array",
                    "description": "List of findings to report",
                    "required": True
                },
                "workflow_name": {
                    "type": "string",
                    "description": "Name of the workflow",
                    "default": "FuzzForge Security Assessment"
                },
                "run_id": {
                    "type": "string",
                    "description": "Run identifier",
                    "required": True
                }
            },
            output_schema={
                "native": {
                    "type": "object",
                    "description": "Native FuzzForge findings format"
                }
            },
            requires_workspace=False  # Reporter doesn't need direct workspace access
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate module configuration"""
        if "findings" not in config and "modules_results" not in config:
            raise ValueError("Either 'findings' or 'modules_results' must be provided")
        return True

    async def execute(self, config: Dict[str, Any], workspace: Path = None) -> ModuleResult:
        """
        Execute the native reporter module.

        Args:
            config: Module configuration with findings
            workspace: Optional workspace path for context

        Returns:
            ModuleResult with native format report
        """
        self.start_timer()
        self.validate_config(config)

        # Get configuration
        workflow_name = config.get("workflow_name", "FuzzForge Security Assessment")
        run_id = config.get("run_id", "unknown")

        # Collect findings from either direct findings or module results
        all_findings = []

        if "findings" in config:
            # Direct findings provided
            all_findings = config["findings"]
            if isinstance(all_findings, list) and all(isinstance(f, dict) for f in all_findings):
                # Convert dict findings to ModuleFinding objects
                all_findings = [ModuleFinding(**f) if isinstance(f, dict) else f for f in all_findings]
        elif "modules_results" in config:
            # Aggregate from module results
            for module_result in config["modules_results"]:
                if isinstance(module_result, dict):
                    findings = module_result.get("findings", [])
                    all_findings.extend(findings)
                elif hasattr(module_result, "findings"):
                    all_findings.extend(module_result.findings)

        logger.info(f"Generating native format report for {len(all_findings)} findings")

        try:
            # Generate native format report
            native_report = self._generate_native_report(
                findings=all_findings,
                workflow_name=workflow_name,
                run_id=run_id
            )

            # Create summary
            summary = self._generate_report_summary(all_findings)

            return ModuleResult(
                module=self.get_metadata().name,
                version=self.get_metadata().version,
                status="success",
                execution_time=self.get_execution_time(),
                findings=[],  # Reporter doesn't generate new findings
                summary=summary,
                metadata={
                    "workflow_name": workflow_name,
                    "run_id": run_id,
                    "report_format": "Native FuzzForge 1.0.0",
                    "total_findings": len(all_findings)
                },
                error=None,
                sarif=native_report  # Field name kept for API compatibility
            )

        except Exception as e:
            logger.error(f"Native reporter failed: {e}")
            return self.create_result(
                findings=[],
                status="failed",
                error=str(e)
            )

    def _generate_native_report(
        self,
        findings: List[ModuleFinding],
        workflow_name: str,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Generate native FuzzForge format report.

        Args:
            findings: List of findings to report
            workflow_name: Name of the workflow
            run_id: Run identifier

        Returns:
            Native FuzzForge formatted dictionary
        """
        # Convert ModuleFinding objects to native format dictionaries
        findings_list = []
        for finding in findings:
            finding_dict = {
                "id": finding.id,
                "rule_id": finding.rule_id,
                "found_by": {
                    "module": finding.found_by.module,
                    "tool_name": finding.found_by.tool_name,
                    "tool_version": finding.found_by.tool_version,
                    "type": finding.found_by.type
                },
                "title": finding.title,
                "description": finding.description,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "category": finding.category,
                "recommendation": finding.recommendation,
                "references": finding.references
            }

            # Add optional fields
            if finding.cwe:
                finding_dict["cwe"] = finding.cwe
            if finding.owasp:
                finding_dict["owasp"] = finding.owasp
            if finding.llm_context:
                finding_dict["llm_context"] = {
                    "model": finding.llm_context.model,
                    "prompt": finding.llm_context.prompt,
                    "temperature": finding.llm_context.temperature
                }

            # Add location if available
            if finding.file_path:
                finding_dict["location"] = {
                    "file": finding.file_path,
                    "line_start": finding.line_start,
                    "line_end": finding.line_end,
                    "column_start": finding.column_start,
                    "column_end": finding.column_end,
                    "snippet": finding.code_snippet
                }

            finding_dict["metadata"] = finding.metadata
            findings_list.append(finding_dict)

        # Create summary
        from datetime import datetime
        summary = self._create_native_summary(findings)

        # Build native format structure
        native_report = {
            "version": "1.0.0",
            "run_id": run_id,
            "workflow": workflow_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "findings": findings_list,
            "summary": summary
        }

        return native_report

    def _create_native_summary(self, findings: List[ModuleFinding]) -> Dict[str, Any]:
        """Create summary for native format"""
        summary = {
            "total_findings": len(findings),
            "by_severity": {},
            "by_confidence": {},
            "by_category": {},
            "by_source": {},
            "by_type": {},
            "affected_files": 0
        }

        affected_files = set()

        for finding in findings:
            # Count by severity
            summary["by_severity"][finding.severity] = summary["by_severity"].get(finding.severity, 0) + 1

            # Count by confidence
            summary["by_confidence"][finding.confidence] = summary["by_confidence"].get(finding.confidence, 0) + 1

            # Count by category
            summary["by_category"][finding.category] = summary["by_category"].get(finding.category, 0) + 1

            # Count by source (module)
            summary["by_source"][finding.found_by.module] = summary["by_source"].get(finding.found_by.module, 0) + 1

            # Count by type
            summary["by_type"][finding.found_by.type] = summary["by_type"].get(finding.found_by.type, 0) + 1

            # Track affected files
            if finding.file_path:
                affected_files.add(finding.file_path)

        summary["affected_files"] = len(affected_files)
        return summary

    # Keep old SARIF methods for reference/future SARIF export module
    def _generate_sarif(
        self,
        findings: List[ModuleFinding],
        tool_name: str,
        tool_version: str,
        include_code_flows: bool,
        workspace_path: str = None
    ) -> Dict[str, Any]:
        """
        Generate SARIF 2.1.0 formatted report.

        Args:
            findings: List of findings to report
            tool_name: Name of the tool
            tool_version: Tool version
            include_code_flows: Whether to include code flow information
            workspace_path: Optional workspace path

        Returns:
            SARIF formatted dictionary
        """
        # Create rules from unique finding types
        rules = self._create_rules(findings)

        # Create results from findings
        results = self._create_results(findings, include_code_flows)

        # Build SARIF structure
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": tool_name,
                            "version": tool_version,
                            "informationUri": "https://fuzzforge.io",
                            "rules": rules
                        }
                    },
                    "results": results,
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "endTimeUtc": datetime.utcnow().isoformat() + "Z"
                        }
                    ]
                }
            ]
        }

        # Add workspace information if available
        if workspace_path:
            sarif["runs"][0]["originalUriBaseIds"] = {
                "WORKSPACE": {
                    "uri": f"file://{workspace_path}/",
                    "description": "The workspace root directory"
                }
            }

        return sarif

    def _create_rules(self, findings: List[ModuleFinding]) -> List[Dict[str, Any]]:
        """
        Create SARIF rules from findings.

        Args:
            findings: List of findings

        Returns:
            List of SARIF rule objects
        """
        rules_dict = {}

        for finding in findings:
            rule_id = f"{finding.category}_{finding.severity}"

            if rule_id not in rules_dict:
                rules_dict[rule_id] = {
                    "id": rule_id,
                    "name": finding.category.replace("_", " ").title(),
                    "shortDescription": {
                        "text": f"{finding.category} vulnerability"
                    },
                    "fullDescription": {
                        "text": f"Detection rule for {finding.category} vulnerabilities with {finding.severity} severity"
                    },
                    "defaultConfiguration": {
                        "level": self._severity_to_sarif_level(finding.severity)
                    },
                    "properties": {
                        "category": finding.category,
                        "severity": finding.severity,
                        "tags": ["security", finding.category, finding.severity]
                    }
                }

        return list(rules_dict.values())

    def _create_results(
        self, findings: List[ModuleFinding], include_code_flows: bool
    ) -> List[Dict[str, Any]]:
        """
        Create SARIF results from findings.

        Args:
            findings: List of findings
            include_code_flows: Whether to include code flows

        Returns:
            List of SARIF result objects
        """
        results = []

        for finding in findings:
            result = {
                "ruleId": f"{finding.category}_{finding.severity}",
                "level": self._severity_to_sarif_level(finding.severity),
                "message": {
                    "text": finding.description
                },
                "locations": []
            }

            # Add location information if available
            if finding.file_path:
                location = {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding.file_path,
                            "uriBaseId": "WORKSPACE"
                        }
                    }
                }

                # Add line information if available
                if finding.line_start:
                    location["physicalLocation"]["region"] = {
                        "startLine": finding.line_start
                    }
                    if finding.line_end:
                        location["physicalLocation"]["region"]["endLine"] = finding.line_end

                    # Add code snippet if available
                    if finding.code_snippet:
                        location["physicalLocation"]["region"]["snippet"] = {
                            "text": finding.code_snippet
                        }

                result["locations"].append(location)

            # Add fix suggestions if available
            if finding.recommendation:
                result["fixes"] = [
                    {
                        "description": {
                            "text": finding.recommendation
                        }
                    }
                ]

            # Add properties
            result["properties"] = {
                "findingId": finding.id,
                "title": finding.title,
                "metadata": finding.metadata
            }

            results.append(result)

        return results

    def _severity_to_sarif_level(self, severity: str) -> str:
        """
        Convert severity to SARIF level.

        Args:
            severity: Finding severity

        Returns:
            SARIF level string
        """
        mapping = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "note",
            "info": "none"
        }
        return mapping.get(severity.lower(), "warning")

    def _generate_report_summary(self, findings: List[ModuleFinding]) -> Dict[str, Any]:
        """
        Generate summary statistics for the report.

        Args:
            findings: List of findings

        Returns:
            Summary dictionary
        """
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        }

        category_counts = {}
        affected_files = set()

        for finding in findings:
            # Count by severity
            if finding.severity in severity_counts:
                severity_counts[finding.severity] += 1

            # Count by category
            if finding.category not in category_counts:
                category_counts[finding.category] = 0
            category_counts[finding.category] += 1

            # Track affected files
            if finding.file_path:
                affected_files.add(finding.file_path)

        return {
            "total_findings": len(findings),
            "severity_distribution": severity_counts,
            "category_distribution": category_counts,
            "affected_files": len(affected_files),
            "report_format": "SARIF 2.1.0",
            "generated_at": datetime.utcnow().isoformat()
        }