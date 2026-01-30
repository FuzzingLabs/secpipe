"""
Android Static Analysis Workflow - Temporal Version

Comprehensive security testing for Android applications using Jadx, OpenGrep, and MobSF.
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

from datetime import timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity interfaces (will be executed by worker)
with workflow.unsafe.imports_passed_through():
    import logging

logger = logging.getLogger(__name__)


@workflow.defn
class AndroidStaticAnalysisWorkflow:
    """
    Android Static Application Security Testing workflow.

    This workflow:
    1. Downloads target (APK) from MinIO
    2. (Optional) Decompiles APK using Jadx
    3. Runs OpenGrep/Semgrep static analysis on decompiled code
    4. (Optional) Runs MobSF comprehensive security scan
    5. Generates a SARIF report with all findings
    6. Uploads results to MinIO
    7. Cleans up cache
    """

    @workflow.run
    async def run(
        self,
        target_id: str,
        apk_path: Optional[str] = None,
        decompile_apk: bool = True,
        jadx_config: Optional[Dict[str, Any]] = None,
        opengrep_config: Optional[Dict[str, Any]] = None,
        mobsf_config: Optional[Dict[str, Any]] = None,
        reporter_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of the uploaded target (APK) in MinIO
            apk_path: Path to APK file within target (if target is not a single APK)
            decompile_apk: Whether to decompile APK with Jadx before OpenGrep
            jadx_config: Configuration for Jadx decompiler
            opengrep_config: Configuration for OpenGrep analyzer
            mobsf_config: Configuration for MobSF scanner
            reporter_config: Configuration for SARIF reporter

        Returns:
            Dictionary containing SARIF report and summary
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting AndroidStaticAnalysisWorkflow "
            f"(workflow_id={workflow_id}, target_id={target_id})"
        )

        # Default configurations
        if not jadx_config:
            jadx_config = {
                "output_dir": "jadx_output",
                "overwrite": True,
                "threads": 4,
                "decompiler_args": []
            }

        if not opengrep_config:
            opengrep_config = {
                "config": "auto",
                "custom_rules_path": "/app/toolbox/modules/android/custom_rules",
                "languages": ["java", "kotlin"],
                "severity": ["ERROR", "WARNING", "INFO"],
                "confidence": ["HIGH", "MEDIUM", "LOW"],
                "timeout": 300,
            }

        if not mobsf_config:
            mobsf_config = {
                "enabled": True,
                "mobsf_url": "http://localhost:8877",
                "api_key": None,
                "rescan": False,
            }

        if not reporter_config:
            reporter_config = {
                "include_code_flows": False
            }

        # Activity retry policy
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )

        # Phase 0: Download target from MinIO
        workflow.logger.info(f"Phase 0: Downloading target from MinIO (target_id={target_id})")
        workspace_path = await workflow.execute_activity(
            "get_target",
            args=[target_id, workflow.info().workflow_id, "shared"],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
        workflow.logger.info(f"✓ Target downloaded to: {workspace_path}")

        # Handle case where workspace_path is a file (single APK upload)
        # vs. a directory containing files
        workspace_path_obj = Path(workspace_path)

        # Determine actual workspace directory and APK path
        if apk_path:
            # User explicitly provided apk_path
            actual_apk_path = apk_path
            # workspace_path could be either a file or directory
            # If it's a file and apk_path matches the filename, use parent as workspace
            if workspace_path_obj.name == apk_path:
                workspace_path = str(workspace_path_obj.parent)
                workflow.logger.info(f"Adjusted workspace to parent directory: {workspace_path}")
        else:
            # No apk_path provided - check if workspace_path is an APK file
            if workspace_path_obj.suffix.lower() == '.apk' or workspace_path_obj.name.endswith('.apk'):
                # workspace_path is the APK file itself
                actual_apk_path = workspace_path_obj.name
                workspace_path = str(workspace_path_obj.parent)
                workflow.logger.info(f"Detected single APK file: {actual_apk_path}, workspace: {workspace_path}")
            else:
                # workspace_path is a directory, need to find APK within it
                actual_apk_path = None
                workflow.logger.info("Workspace is a directory, APK detection will be handled by modules")

        # Phase 1: Jadx decompilation (if enabled and APK provided)
        jadx_result = None
        analysis_workspace = workspace_path

        if decompile_apk and actual_apk_path:
            workflow.logger.info(f"Phase 1: Decompiling APK with Jadx (apk={actual_apk_path})")

            jadx_activity_config = {
                **jadx_config,
                "apk_path": actual_apk_path
            }

            jadx_result = await workflow.execute_activity(
                "decompile_with_jadx",
                args=[workspace_path, jadx_activity_config],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=retry_policy,
            )

            if jadx_result.get("status") == "success":
                # Use decompiled sources as workspace for OpenGrep
                source_dir = jadx_result.get("summary", {}).get("source_dir")
                if source_dir:
                    analysis_workspace = source_dir
                    workflow.logger.info(
                        f"✓ Jadx decompiled {jadx_result.get('summary', {}).get('java_files', 0)} Java files"
                    )
            else:
                workflow.logger.warning(f"Jadx decompilation failed: {jadx_result.get('error')}")
        else:
            workflow.logger.info("Phase 1: Jadx decompilation skipped")

        # Phase 2: OpenGrep static analysis
        workflow.logger.info(f"Phase 2: OpenGrep analysis on {analysis_workspace}")

        opengrep_result = await workflow.execute_activity(
            "scan_with_opengrep",
            args=[analysis_workspace, opengrep_config],
            start_to_close_timeout=timedelta(minutes=20),
            retry_policy=retry_policy,
        )

        workflow.logger.info(
            f"✓ OpenGrep completed: {opengrep_result.get('summary', {}).get('total_findings', 0)} findings"
        )

        # Phase 3: MobSF analysis (if enabled and APK provided)
        mobsf_result = None

        if mobsf_config.get("enabled", True) and actual_apk_path:
            workflow.logger.info(f"Phase 3: MobSF scan on APK: {actual_apk_path}")

            mobsf_activity_config = {
                **mobsf_config,
                "file_path": actual_apk_path
            }

            try:
                mobsf_result = await workflow.execute_activity(
                    "scan_with_mobsf",
                    args=[workspace_path, mobsf_activity_config],
                    start_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2  # MobSF can be flaky, limit retries
                    ),
                )

                # Handle skipped or completed status
                if mobsf_result.get("status") == "skipped":
                    workflow.logger.warning(
                        f"⚠️  MobSF skipped: {mobsf_result.get('summary', {}).get('skip_reason', 'Unknown reason')}"
                    )
                else:
                    workflow.logger.info(
                        f"✓ MobSF completed: {mobsf_result.get('summary', {}).get('total_findings', 0)} findings"
                    )
            except Exception as e:
                workflow.logger.warning(f"MobSF scan failed (continuing without it): {e}")
                mobsf_result = None
        else:
            workflow.logger.info("Phase 3: MobSF scan skipped (disabled or no APK)")

        # Phase 4: Generate SARIF report
        workflow.logger.info("Phase 4: Generating SARIF report")

        sarif_report = await workflow.execute_activity(
            "generate_android_sarif",
            args=[jadx_result or {}, opengrep_result, mobsf_result, reporter_config, workspace_path],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        # Phase 5: Upload results to MinIO
        workflow.logger.info("Phase 5: Uploading results to MinIO")

        result_url = await workflow.execute_activity(
            "upload_results",
            args=[workflow.info().workflow_id, sarif_report, "sarif"],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        workflow.logger.info(f"✓ Results uploaded: {result_url}")

        # Phase 6: Cleanup cache
        workflow.logger.info("Phase 6: Cleaning up cache")

        await workflow.execute_activity(
            "cleanup_cache",
            args=[workspace_path, "shared"],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),  # Don't retry cleanup
        )

        # Calculate summary
        total_findings = len(sarif_report.get("runs", [{}])[0].get("results", []))

        summary = {
            "workflow": "android_static_analysis",
            "target_id": target_id,
            "total_findings": total_findings,
            "decompiled_java_files": (jadx_result or {}).get("summary", {}).get("java_files", 0) if jadx_result else 0,
            "opengrep_findings": opengrep_result.get("summary", {}).get("total_findings", 0),
            "mobsf_findings": mobsf_result.get("summary", {}).get("total_findings", 0) if mobsf_result else 0,
            "result_url": result_url,
        }

        workflow.logger.info(
            f"✅ AndroidStaticAnalysisWorkflow completed successfully: {total_findings} findings"
        )

        return {
            "sarif": sarif_report,
            "summary": summary,
        }
