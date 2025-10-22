"""
Python SAST Workflow Activities

Activities specific to the Python SAST workflow:
- scan_dependencies_activity: Scan Python dependencies for CVEs using pip-audit
- analyze_with_bandit_activity: Analyze Python code for security issues using Bandit
- analyze_with_mypy_activity: Analyze Python code for type safety using Mypy
- generate_python_sast_sarif_activity: Generate SARIF report from all findings
"""

import logging
import sys
from pathlib import Path

from temporalio import activity

# Configure logging
logger = logging.getLogger(__name__)

# Add toolbox to path for module imports
sys.path.insert(0, '/app/toolbox')


@activity.defn(name="scan_dependencies")
async def scan_dependencies_activity(workspace_path: str, config: dict) -> dict:
    """
    Scan Python dependencies for known vulnerabilities using pip-audit.

    Args:
        workspace_path: Path to the workspace directory
        config: DependencyScanner configuration

    Returns:
        Scanner results dictionary
    """
    logger.info(f"Activity: scan_dependencies (workspace={workspace_path})")

    try:
        from modules.scanner import DependencyScanner

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        scanner = DependencyScanner()
        result = await scanner.execute(config, workspace)

        logger.info(
            f"✓ Dependency scanning completed: "
            f"{result.summary.get('total_vulnerabilities', 0)} vulnerabilities found"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"Dependency scanning failed: {e}", exc_info=True)
        raise


@activity.defn(name="analyze_with_bandit")
async def analyze_with_bandit_activity(workspace_path: str, config: dict) -> dict:
    """
    Analyze Python code for security issues using Bandit.

    Args:
        workspace_path: Path to the workspace directory
        config: BanditAnalyzer configuration

    Returns:
        Analysis results dictionary
    """
    logger.info(f"Activity: analyze_with_bandit (workspace={workspace_path})")

    try:
        from modules.analyzer import BanditAnalyzer

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        analyzer = BanditAnalyzer()
        result = await analyzer.execute(config, workspace)

        logger.info(
            f"✓ Bandit analysis completed: "
            f"{result.summary.get('total_issues', 0)} security issues found"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"Bandit analysis failed: {e}", exc_info=True)
        raise


@activity.defn(name="analyze_with_mypy")
async def analyze_with_mypy_activity(workspace_path: str, config: dict) -> dict:
    """
    Analyze Python code for type safety issues using Mypy.

    Args:
        workspace_path: Path to the workspace directory
        config: MypyAnalyzer configuration

    Returns:
        Analysis results dictionary
    """
    logger.info(f"Activity: analyze_with_mypy (workspace={workspace_path})")

    try:
        from modules.analyzer import MypyAnalyzer

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        analyzer = MypyAnalyzer()
        result = await analyzer.execute(config, workspace)

        logger.info(
            f"✓ Mypy analysis completed: "
            f"{result.summary.get('total_errors', 0)} type errors found"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"Mypy analysis failed: {e}", exc_info=True)
        raise


@activity.defn(name="generate_python_sast_sarif")
async def generate_python_sast_sarif_activity(
    dependency_results: dict,
    bandit_results: dict,
    mypy_results: dict,
    config: dict,
    workspace_path: str
) -> dict:
    """
    Generate SARIF report from all SAST analysis results.

    Args:
        dependency_results: Results from dependency scanner
        bandit_results: Results from Bandit analyzer
        mypy_results: Results from Mypy analyzer
        config: Reporter configuration
        workspace_path: Path to the workspace

    Returns:
        SARIF report dictionary
    """
    logger.info("Activity: generate_python_sast_sarif")

    try:
        from modules.reporter import SARIFReporter

        workspace = Path(workspace_path)

        # Combine findings from all modules
        all_findings = []

        # Add dependency scanner findings
        dependency_findings = dependency_results.get("findings", [])
        all_findings.extend(dependency_findings)

        # Add Bandit findings
        bandit_findings = bandit_results.get("findings", [])
        all_findings.extend(bandit_findings)

        # Add Mypy findings
        mypy_findings = mypy_results.get("findings", [])
        all_findings.extend(mypy_findings)

        # Prepare reporter config
        reporter_config = {
            **config,
            "findings": all_findings,
            "tool_name": "FuzzForge Python SAST",
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
