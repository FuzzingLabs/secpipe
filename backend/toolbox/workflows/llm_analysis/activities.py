"""
LLM Analysis Workflow Activities
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
    from toolbox.modules.analyzer.llm_analyzer import LLMAnalyzer
except ImportError:
    try:
        from modules.analyzer.llm_analyzer import LLMAnalyzer
    except ImportError:
        from src.toolbox.modules.analyzer.llm_analyzer import LLMAnalyzer

logger = logging.getLogger(__name__)


@activity.defn(name="llm_generate_sarif")
async def llm_generate_sarif(findings: list, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate SARIF report from LLM findings.

    Args:
        findings: List of finding dictionaries
        metadata: Metadata including tool_name, tool_version, run_id

    Returns:
        SARIF report dictionary
    """
    activity.logger.info(f"Generating SARIF report from {len(findings)} findings")

    # Basic SARIF 2.1.0 structure
    sarif_report = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": metadata.get("tool_name", "llm-analyzer"),
                        "version": metadata.get("tool_version", "1.0.0"),
                        "informationUri": "https://github.com/FuzzingLabs/fuzzforge_ai"
                    }
                },
                "results": []
            }
        ]
    }

    # Convert findings to SARIF results
    for finding in findings:
        sarif_result = {
            "ruleId": finding.get("id", "unknown"),
            "level": _severity_to_sarif_level(finding.get("severity", "warning")),
            "message": {
                "text": finding.get("title", "Security issue detected")
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
                if finding.get("line_end"):
                    location["physicalLocation"]["region"]["endLine"] = finding["line_end"]

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


@activity.defn(name="analyze_with_llm")
async def analyze_with_llm(target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze code using LLM.

    Args:
        target_path: Path to the workspace containing code
        config: LLM analyzer configuration

    Returns:
        Dictionary containing findings and summary
    """
    activity.logger.info(f"Starting LLM analysis: {target_path}")
    activity.logger.info(f"Config: {config}")

    workspace = Path(target_path)

    if not workspace.exists():
        raise FileNotFoundError(f"Workspace not found: {target_path}")

    # Create and execute LLM analyzer
    analyzer = LLMAnalyzer()

    # Validate configuration
    analyzer.validate_config(config)

    # Execute analysis
    result = await analyzer.execute(config, workspace)

    if result.status == "failed":
        raise RuntimeError(f"LLM analysis failed: {result.error or 'Unknown error'}")

    activity.logger.info(
        f"LLM analysis completed: {len(result.findings)} findings from "
        f"{result.summary.get('files_analyzed', 0)} files"
    )

    # Convert ModuleFinding objects to dicts for serialization
    findings_dicts = [finding.model_dump() for finding in result.findings]

    return {
        "findings": findings_dicts,
        "summary": result.summary
    }
