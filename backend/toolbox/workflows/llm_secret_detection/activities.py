"""LLM Secret Detection Workflow Activities"""

from pathlib import Path
from typing import Dict, Any
from temporalio import activity

try:
    from toolbox.modules.secret_detection.llm_secret_detector import LLMSecretDetectorModule
except ImportError:
    from modules.secret_detection.llm_secret_detector import LLMSecretDetectorModule

@activity.defn(name="scan_with_llm")
async def scan_with_llm(target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Scan code using LLM."""
    activity.logger.info(f"Starting LLM secret detection: {target_path}")
    workspace = Path(target_path)

    llm_detector = LLMSecretDetectorModule()
    llm_detector.validate_config(config)
    result = await llm_detector.execute(config, workspace)

    if result.status == "failed":
        raise RuntimeError(f"LLM detection failed: {result.error}")

    findings_dicts = [finding.model_dump() for finding in result.findings]
    return {"findings": findings_dicts, "summary": result.summary}


@activity.defn(name="llm_secret_generate_sarif")
async def llm_secret_generate_sarif(findings: list, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate SARIF report from LLM secret detection findings.

    Args:
        findings: List of finding dictionaries from LLM secret detector
        metadata: Metadata including tool_name, tool_version

    Returns:
        SARIF 2.1.0 report dictionary
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
                        "name": metadata.get("tool_name", "llm-secret-detector"),
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
            "ruleId": finding.get("id", finding.get("metadata", {}).get("secret_type", "unknown-secret")),
            "level": _severity_to_sarif_level(finding.get("severity", "warning")),
            "message": {
                "text": finding.get("title", "Secret detected by LLM")
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
