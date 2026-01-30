"""TruffleHog Detection Workflow Activities"""

from pathlib import Path
from typing import Dict, Any
from temporalio import activity

try:
    from toolbox.modules.secret_detection.trufflehog import TruffleHogModule
except ImportError:
    from modules.secret_detection.trufflehog import TruffleHogModule

@activity.defn(name="scan_with_trufflehog")
async def scan_with_trufflehog(target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Scan code using TruffleHog."""
    activity.logger.info(f"Starting TruffleHog scan: {target_path}")
    workspace = Path(target_path)

    trufflehog = TruffleHogModule()
    trufflehog.validate_config(config)
    result = await trufflehog.execute(config, workspace)

    if result.status == "failed":
        raise RuntimeError(f"TruffleHog scan failed: {result.error}")

    findings_dicts = [finding.model_dump() for finding in result.findings]
    return {"findings": findings_dicts, "summary": result.summary}


@activity.defn(name="trufflehog_generate_sarif")
async def trufflehog_generate_sarif(findings: list, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate SARIF report from TruffleHog findings.

    Args:
        findings: List of finding dictionaries
        metadata: Metadata including tool_name, tool_version

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
                        "name": metadata.get("tool_name", "trufflehog"),
                        "version": metadata.get("tool_version", "3.63.2"),
                        "informationUri": "https://github.com/trufflesecurity/trufflehog"
                    }
                },
                "results": []
            }
        ]
    }

    # Convert findings to SARIF results
    for finding in findings:
        sarif_result = {
            "ruleId": finding.get("metadata", {}).get("detector", "unknown"),
            "level": _severity_to_sarif_level(finding.get("severity", "warning")),
            "message": {
                "text": finding.get("title", "Secret detected")
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
