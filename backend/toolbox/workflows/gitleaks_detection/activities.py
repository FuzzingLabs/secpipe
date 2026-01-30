"""
Gitleaks Detection Workflow Activities
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
from typing import Dict, Any

from temporalio import activity

try:
    from toolbox.modules.secret_detection.gitleaks import GitleaksModule
except ImportError:
    try:
        from modules.secret_detection.gitleaks import GitleaksModule
    except ImportError:
        from src.toolbox.modules.secret_detection.gitleaks import GitleaksModule

logger = logging.getLogger(__name__)


@activity.defn(name="scan_with_gitleaks")
async def scan_with_gitleaks(target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan code using Gitleaks.

    Args:
        target_path: Path to the workspace containing code
        config: Gitleaks configuration

    Returns:
        Dictionary containing findings and summary
    """
    activity.logger.info(f"Starting Gitleaks scan: {target_path}")
    activity.logger.info(f"Config: {config}")

    workspace = Path(target_path)

    if not workspace.exists():
        raise FileNotFoundError(f"Workspace not found: {target_path}")

    # Create and execute Gitleaks module
    gitleaks = GitleaksModule()

    # Validate configuration
    gitleaks.validate_config(config)

    # Execute scan
    result = await gitleaks.execute(config, workspace)

    if result.status == "failed":
        raise RuntimeError(f"Gitleaks scan failed: {result.error or 'Unknown error'}")

    activity.logger.info(
        f"Gitleaks scan completed: {len(result.findings)} findings from "
        f"{result.summary.get('files_scanned', 0)} files"
    )

    # Convert ModuleFinding objects to dicts for serialization
    findings_dicts = [finding.model_dump() for finding in result.findings]

    return {
        "findings": findings_dicts,
        "summary": result.summary
    }


@activity.defn(name="gitleaks_generate_sarif")
async def gitleaks_generate_sarif(findings: list, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate SARIF report from Gitleaks findings.

    Args:
        findings: List of finding dictionaries
        metadata: Metadata including tool_name, tool_version, run_id

    Returns:
        SARIF report dictionary
    """
    activity.logger.info(f"Generating SARIF report from {len(findings)} findings")

    # Debug: Check if first finding has line_start
    if findings:
        first_finding = findings[0]
        activity.logger.info(f"First finding keys: {list(first_finding.keys())}")
        activity.logger.info(f"line_start value: {first_finding.get('line_start')}")

    # Basic SARIF 2.1.0 structure
    sarif_report = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": metadata.get("tool_name", "gitleaks"),
                        "version": metadata.get("tool_version", "8.18.0"),
                        "informationUri": "https://github.com/gitleaks/gitleaks"
                    }
                },
                "results": []
            }
        ]
    }

    # Convert findings to SARIF results
    for finding in findings:
        sarif_result = {
            "ruleId": finding.get("metadata", {}).get("rule_id", "unknown"),
            "level": _severity_to_sarif_level(finding.get("severity", "warning")),
            "message": {
                "text": finding.get("title", "Secret leak detected")
            },
            "locations": []
        }

        # Add description if present
        if finding.get("description"):
            sarif_result["message"]["markdown"] = finding["description"]

        # Add location if file path is present
        if finding.get("file_path"):
            location = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": finding["file_path"]
                    }
                }
            }

            # Add region if line number is present
            if finding.get("line_start"):
                location["physicalLocation"]["region"] = {
                    "startLine": finding["line_start"]
                }

            sarif_result["locations"].append(location)

        sarif_report["runs"][0]["results"].append(sarif_result)

    activity.logger.info(f"Generated SARIF report with {len(sarif_report['runs'][0]['results'])} results")

    return sarif_report


def _severity_to_sarif_level(severity: str) -> str:
    """Convert severity to SARIF level"""
    severity_map = {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
        "info": "note"
    }
    return severity_map.get(severity.lower(), "warning")
