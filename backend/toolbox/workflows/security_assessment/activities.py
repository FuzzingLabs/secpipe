"""
Security Assessment Workflow Activities

Activities specific to the security assessment workflow:
- scan_files_activity: Scan files in the workspace
- analyze_security_activity: Analyze security vulnerabilities
- generate_sarif_report_activity: Generate SARIF report from findings
"""

import logging
import sys
from pathlib import Path

from temporalio import activity

# Configure logging
logger = logging.getLogger(__name__)

# Add toolbox to path for module imports
sys.path.insert(0, '/app/toolbox')


@activity.defn(name="scan_files")
async def scan_files_activity(workspace_path: str, config: dict) -> dict:
    """
    Scan files in the workspace.

    Args:
        workspace_path: Path to the workspace directory
        config: Scanner configuration

    Returns:
        Scanner results dictionary
    """
    logger.info(f"Activity: scan_files (workspace={workspace_path})")

    try:
        from modules.scanner import FileScanner

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        scanner = FileScanner()
        result = await scanner.execute(config, workspace)

        logger.info(
            f"✓ File scanning completed: "
            f"{result.summary.get('total_files', 0)} files scanned"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"File scanning failed: {e}", exc_info=True)
        raise


@activity.defn(name="analyze_security")
async def analyze_security_activity(workspace_path: str, config: dict) -> dict:
    """
    Analyze security vulnerabilities in the workspace.

    Args:
        workspace_path: Path to the workspace directory
        config: Analyzer configuration

    Returns:
        Analysis results dictionary
    """
    logger.info(f"Activity: analyze_security (workspace={workspace_path})")

    try:
        from modules.analyzer import SecurityAnalyzer

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        analyzer = SecurityAnalyzer()
        result = await analyzer.execute(config, workspace)

        logger.info(
            f"✓ Security analysis completed: "
            f"{result.summary.get('total_findings', 0)} findings"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"Security analysis failed: {e}", exc_info=True)
        raise


@activity.defn(name="generate_sarif_report")
async def generate_sarif_report_activity(
    scan_results: dict,
    analysis_results: dict,
    config: dict,
    workspace_path: str
) -> dict:
    """
    Generate SARIF report from scan and analysis results.

    Args:
        scan_results: Results from file scanner
        analysis_results: Results from security analyzer
        config: Reporter configuration
        workspace_path: Path to the workspace

    Returns:
        SARIF report dictionary
    """
    logger.info("Activity: generate_sarif_report")

    try:
        from modules.reporter import SARIFReporter

        workspace = Path(workspace_path)

        # Combine findings from all modules
        all_findings = []

        # Add scanner findings (only sensitive files, not all files)
        scanner_findings = scan_results.get("findings", [])
        sensitive_findings = [f for f in scanner_findings if f.get("severity") != "info"]
        all_findings.extend(sensitive_findings)

        # Add analyzer findings
        analyzer_findings = analysis_results.get("findings", [])
        all_findings.extend(analyzer_findings)

        # Prepare reporter config
        reporter_config = {
            **config,
            "findings": all_findings,
            "tool_name": "FuzzForge Security Assessment",
            "tool_version": "1.0.0"
        }

        reporter = SARIFReporter()
        result = await reporter.execute(reporter_config, workspace)

        # Extract SARIF from result
        sarif = result.dict().get("sarif", {})

        logger.info(f"✓ SARIF report generated with {len(all_findings)} findings")
        return sarif

    except Exception as e:
        logger.error(f"SARIF report generation failed: {e}", exc_info=True)
        raise
