"""
Android Static Analysis Workflow Activities

Activities for the Android security testing workflow:
- decompile_with_jadx_activity: Decompile APK using Jadx
- scan_with_opengrep_activity: Analyze code with OpenGrep/Semgrep
- scan_with_mobsf_activity: Scan APK with MobSF
- generate_android_sarif_activity: Generate combined SARIF report
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
import sys
from pathlib import Path

from temporalio import activity

# Configure logging
logger = logging.getLogger(__name__)

# Add toolbox to path for module imports
sys.path.insert(0, '/app/toolbox')


@activity.defn(name="decompile_with_jadx")
async def decompile_with_jadx_activity(workspace_path: str, config: dict) -> dict:
    """
    Decompile Android APK to Java source code using Jadx.

    Args:
        workspace_path: Path to the workspace directory
        config: JadxDecompiler configuration

    Returns:
        Decompilation results dictionary
    """
    logger.info(f"Activity: decompile_with_jadx (workspace={workspace_path})")

    try:
        from modules.android import JadxDecompiler

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        decompiler = JadxDecompiler()
        result = await decompiler.execute(config, workspace)

        logger.info(
            f"✓ Jadx decompilation completed: "
            f"{result.summary.get('java_files', 0)} Java files generated"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"Jadx decompilation failed: {e}", exc_info=True)
        raise


@activity.defn(name="scan_with_opengrep")
async def scan_with_opengrep_activity(workspace_path: str, config: dict) -> dict:
    """
    Analyze Android code for security issues using OpenGrep/Semgrep.

    Args:
        workspace_path: Path to the workspace directory
        config: OpenGrepAndroid configuration

    Returns:
        Analysis results dictionary
    """
    logger.info(f"Activity: scan_with_opengrep (workspace={workspace_path})")

    try:
        from modules.android import OpenGrepAndroid

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        analyzer = OpenGrepAndroid()
        result = await analyzer.execute(config, workspace)

        logger.info(
            f"✓ OpenGrep analysis completed: "
            f"{result.summary.get('total_findings', 0)} security issues found"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"OpenGrep analysis failed: {e}", exc_info=True)
        raise


@activity.defn(name="scan_with_mobsf")
async def scan_with_mobsf_activity(workspace_path: str, config: dict) -> dict:
    """
    Analyze Android APK for security issues using MobSF.

    Args:
        workspace_path: Path to the workspace directory
        config: MobSFScanner configuration

    Returns:
        Scan results dictionary (or skipped status if MobSF unavailable)
    """
    logger.info(f"Activity: scan_with_mobsf (workspace={workspace_path})")

    # Check if MobSF is installed (graceful degradation for ARM64 platform)
    mobsf_path = Path("/app/mobsf")
    if not mobsf_path.exists():
        logger.warning("MobSF not installed on this platform (ARM64/Rosetta limitation)")
        return {
            "status": "skipped",
            "findings": [],
            "summary": {
                "total_findings": 0,
                "skip_reason": "MobSF unavailable on ARM64 platform (Rosetta 2 incompatibility)"
            }
        }

    try:
        from modules.android import MobSFScanner

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        scanner = MobSFScanner()
        result = await scanner.execute(config, workspace)

        logger.info(
            f"✓ MobSF scan completed: "
            f"{result.summary.get('total_findings', 0)} findings"
        )
        return result.dict()

    except Exception as e:
        logger.error(f"MobSF scan failed: {e}", exc_info=True)
        raise


@activity.defn(name="generate_android_sarif")
async def generate_android_sarif_activity(
    jadx_result: dict,
    opengrep_result: dict,
    mobsf_result: dict,
    config: dict,
    workspace_path: str
) -> dict:
    """
    Generate combined SARIF report from all Android security findings.

    Args:
        jadx_result: Jadx decompilation results
        opengrep_result: OpenGrep analysis results
        mobsf_result: MobSF scan results (may be None if disabled)
        config: Reporter configuration
        workspace_path: Workspace path

    Returns:
        SARIF report dictionary
    """
    logger.info("Activity: generate_android_sarif")

    try:
        from modules.reporter import SARIFReporter

        workspace = Path(workspace_path)

        # Collect all findings
        all_findings = []
        all_findings.extend(opengrep_result.get("findings", []))

        if mobsf_result:
            all_findings.extend(mobsf_result.get("findings", []))

        # Prepare reporter config
        reporter_config = {
            **(config or {}),
            "findings": all_findings,
            "tool_name": "FuzzForge Android Static Analysis",
            "tool_version": "1.0.0",
            "metadata": {
                "jadx_version": "1.5.0",
                "opengrep_version": "1.45.0",
                "mobsf_version": "3.9.7",
                "java_files_decompiled": jadx_result.get("summary", {}).get("java_files", 0),
            }
        }

        reporter = SARIFReporter()
        result = await reporter.execute(reporter_config, workspace)

        sarif_report = result.dict().get("sarif", {})

        logger.info(f"✓ SARIF report generated with {len(all_findings)} findings")

        return sarif_report

    except Exception as e:
        logger.error(f"SARIF report generation failed: {e}", exc_info=True)
        raise
