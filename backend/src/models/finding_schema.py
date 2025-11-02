"""
FuzzForge Native Finding Format Schema

This module defines the native finding format used internally by FuzzForge.
This format is more expressive than SARIF and optimized for security testing workflows.
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

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class FoundBy(BaseModel):
    """Information about who/what found the vulnerability"""
    module: str = Field(..., description="FuzzForge module that detected the finding (e.g., 'semgrep_scanner', 'llm_analysis')")
    tool_name: str = Field(..., description="Name of the underlying tool (e.g., 'Semgrep', 'Claude-3.5-Sonnet', 'MobSF')")
    tool_version: str = Field(..., description="Version of the tool")
    type: Literal["llm", "tool", "fuzzer", "manual"] = Field(..., description="Type of detection method")


class LLMContext(BaseModel):
    """Context information for LLM-detected findings"""
    model: str = Field(..., description="LLM model used (e.g., 'claude-3-5-sonnet-20250129')")
    prompt: str = Field(..., description="Prompt or analysis instructions used")
    temperature: Optional[float] = Field(None, description="Temperature parameter used for generation")


class Location(BaseModel):
    """Location information for a finding"""
    file: str = Field(..., description="File path relative to workspace root")
    line_start: Optional[int] = Field(None, description="Starting line number (1-indexed)")
    line_end: Optional[int] = Field(None, description="Ending line number (1-indexed)")
    column_start: Optional[int] = Field(None, description="Starting column number (1-indexed)")
    column_end: Optional[int] = Field(None, description="Ending column number (1-indexed)")
    snippet: Optional[str] = Field(None, description="Code snippet at the location")


class Finding(BaseModel):
    """Individual security finding"""
    id: str = Field(..., description="Unique finding identifier (UUID)")
    rule_id: str = Field(..., description="Rule/pattern identifier (e.g., 'sql_injection', 'hardcoded_secret')")
    found_by: FoundBy = Field(..., description="Detection attribution")
    llm_context: Optional[LLMContext] = Field(None, description="LLM-specific context (only if found_by.type == 'llm')")

    title: str = Field(..., description="Short finding title")
    description: str = Field(..., description="Detailed description of the finding")

    severity: Literal["critical", "high", "medium", "low", "info"] = Field(..., description="Severity level")
    confidence: Literal["high", "medium", "low"] = Field(..., description="Confidence level in the finding")

    category: str = Field(..., description="Finding category (e.g., 'injection', 'authentication', 'cryptography')")
    cwe: Optional[str] = Field(None, description="CWE identifier (e.g., 'CWE-89')")
    owasp: Optional[str] = Field(None, description="OWASP category (e.g., 'A03:2021-Injection')")

    location: Optional[Location] = Field(None, description="Location of the finding in source code")

    recommendation: Optional[str] = Field(None, description="Remediation recommendation")
    references: List[str] = Field(default_factory=list, description="External references (URLs, documentation)")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class FindingsSummary(BaseModel):
    """Summary statistics for findings"""
    total_findings: int = Field(..., description="Total number of findings")
    by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity level")
    by_confidence: Dict[str, int] = Field(default_factory=dict, description="Count by confidence level")
    by_category: Dict[str, int] = Field(default_factory=dict, description="Count by category")
    by_source: Dict[str, int] = Field(default_factory=dict, description="Count by detection source (module name)")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Count by detection type (llm/tool/fuzzer)")
    affected_files: int = Field(0, description="Number of unique files with findings")


class FuzzForgeFindingsReport(BaseModel):
    """Native FuzzForge findings report format"""
    version: str = Field(default="1.0.0", description="Format version")
    run_id: str = Field(..., description="Workflow run identifier")
    workflow: str = Field(..., description="Workflow name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Report generation timestamp")

    findings: List[Finding] = Field(default_factory=list, description="List of security findings")
    summary: FindingsSummary = Field(..., description="Summary statistics")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional report metadata")


# JSON Schema export for documentation
FINDING_SCHEMA_VERSION = "1.0.0"

def get_json_schema() -> Dict[str, Any]:
    """Get JSON schema for the FuzzForge findings format"""
    return FuzzForgeFindingsReport.model_json_schema()


def validate_findings_report(data: Dict[str, Any]) -> FuzzForgeFindingsReport:
    """
    Validate a findings report against the schema

    Args:
        data: Dictionary containing findings report data

    Returns:
        Validated FuzzForgeFindingsReport object

    Raises:
        ValidationError: If data doesn't match schema
    """
    return FuzzForgeFindingsReport(**data)


def create_summary(findings: List[Finding]) -> FindingsSummary:
    """
    Generate summary statistics from a list of findings

    Args:
        findings: List of Finding objects

    Returns:
        FindingsSummary with aggregated statistics
    """
    summary = FindingsSummary(
        total_findings=len(findings),
        by_severity={},
        by_confidence={},
        by_category={},
        by_source={},
        by_type={},
        affected_files=0
    )

    affected_files = set()

    for finding in findings:
        # Count by severity
        summary.by_severity[finding.severity] = summary.by_severity.get(finding.severity, 0) + 1

        # Count by confidence
        summary.by_confidence[finding.confidence] = summary.by_confidence.get(finding.confidence, 0) + 1

        # Count by category
        summary.by_category[finding.category] = summary.by_category.get(finding.category, 0) + 1

        # Count by source (module)
        summary.by_source[finding.found_by.module] = summary.by_source.get(finding.found_by.module, 0) + 1

        # Count by type
        summary.by_type[finding.found_by.type] = summary.by_type.get(finding.found_by.type, 0) + 1

        # Track affected files
        if finding.location and finding.location.file:
            affected_files.add(finding.location.file)

    summary.affected_files = len(affected_files)

    return summary
