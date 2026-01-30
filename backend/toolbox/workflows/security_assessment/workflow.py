"""
Security Assessment Workflow - Temporal Version

Comprehensive security analysis using multiple modules.
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

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity interfaces (will be executed by worker)
with workflow.unsafe.imports_passed_through():
    import logging

logger = logging.getLogger(__name__)


@workflow.defn
class SecurityAssessmentWorkflow:
    """
    Comprehensive security assessment workflow.

    This workflow:
    1. Downloads target from MinIO
    2. Scans files in the workspace
    3. Analyzes code for security vulnerabilities
    4. Generates a SARIF report with all findings
    5. Uploads results to MinIO
    6. Cleans up cache
    """

    @workflow.run
    async def run(
        self,
        target_id: str,
        scanner_config: Optional[Dict[str, Any]] = None,
        analyzer_config: Optional[Dict[str, Any]] = None,
        reporter_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of the uploaded target in MinIO
            scanner_config: Configuration for file scanner
            analyzer_config: Configuration for security analyzer
            reporter_config: Configuration for SARIF reporter

        Returns:
            Dictionary containing SARIF report and summary
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting SecurityAssessmentWorkflow "
            f"(workflow_id={workflow_id}, target_id={target_id})"
        )

        # Default configurations
        if not scanner_config:
            scanner_config = {
                "patterns": ["*"],
                "check_sensitive": True,
                "calculate_hashes": False,
                "max_file_size": 10485760  # 10MB
            }

        if not analyzer_config:
            analyzer_config = {
                "file_extensions": [".py", ".js", ".java", ".php", ".rb", ".go"],
                "check_secrets": True,
                "check_sql": True,
                "check_dangerous_functions": True
            }

        if not reporter_config:
            reporter_config = {
                "include_code_flows": False
            }

        results = {
            "workflow_id": workflow_id,
            "target_id": target_id,
            "status": "running",
            "steps": []
        }

        try:
            # Get run ID for workspace isolation (using shared mode for read-only analysis)
            run_id = workflow.info().run_id

            # Step 1: Download target from MinIO
            workflow.logger.info("Step 1: Downloading target from MinIO")
            target_path = await workflow.execute_activity(
                "get_target",
                args=[target_id, run_id, "shared"],  # target_id, run_id, workspace_isolation
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )
            results["steps"].append({
                "step": "download_target",
                "status": "success",
                "target_path": target_path
            })
            workflow.logger.info(f"✓ Target downloaded to: {target_path}")

            # Step 2: File scanning
            workflow.logger.info("Step 2: Scanning files")
            scan_results = await workflow.execute_activity(
                "scan_files",
                args=[target_path, scanner_config],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )
            results["steps"].append({
                "step": "file_scanning",
                "status": "success",
                "files_scanned": scan_results.get("summary", {}).get("total_files", 0)
            })
            workflow.logger.info(
                f"✓ File scanning completed: "
                f"{scan_results.get('summary', {}).get('total_files', 0)} files"
            )

            # Step 3: Security analysis
            workflow.logger.info("Step 3: Analyzing security vulnerabilities")
            analysis_results = await workflow.execute_activity(
                "analyze_security",
                args=[target_path, analyzer_config],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )
            results["steps"].append({
                "step": "security_analysis",
                "status": "success",
                "findings": analysis_results.get("summary", {}).get("total_findings", 0)
            })
            workflow.logger.info(
                f"✓ Security analysis completed: "
                f"{analysis_results.get('summary', {}).get('total_findings', 0)} findings"
            )

            # Step 4: Generate SARIF report
            workflow.logger.info("Step 4: Generating SARIF report")
            sarif_report = await workflow.execute_activity(
                "generate_sarif_report",
                args=[scan_results, analysis_results, reporter_config, target_path],
                start_to_close_timeout=timedelta(minutes=5)
            )
            results["steps"].append({
                "step": "report_generation",
                "status": "success"
            })

            # Count total findings in SARIF
            total_findings = 0
            if sarif_report and "runs" in sarif_report:
                total_findings = len(sarif_report["runs"][0].get("results", []))

            workflow.logger.info(f"✓ SARIF report generated with {total_findings} findings")

            # Step 5: Upload results to MinIO
            workflow.logger.info("Step 5: Uploading results")
            try:
                results_url = await workflow.execute_activity(
                    "upload_results",
                    args=[workflow_id, sarif_report, "sarif"],
                    start_to_close_timeout=timedelta(minutes=2)
                )
                results["results_url"] = results_url
                workflow.logger.info(f"✓ Results uploaded to: {results_url}")
            except Exception as e:
                workflow.logger.warning(f"Failed to upload results: {e}")
                results["results_url"] = None

            # Step 6: Cleanup cache
            workflow.logger.info("Step 6: Cleaning up cache")
            try:
                await workflow.execute_activity(
                    "cleanup_cache",
                    args=[target_path, "shared"],  # target_path, workspace_isolation
                    start_to_close_timeout=timedelta(minutes=1)
                )
                workflow.logger.info("✓ Cache cleaned up (skipped for shared mode)")
            except Exception as e:
                workflow.logger.warning(f"Cache cleanup failed: {e}")

            # Mark workflow as successful
            results["status"] = "success"
            results["sarif"] = sarif_report
            results["summary"] = {
                "total_findings": total_findings,
                "files_scanned": scan_results.get("summary", {}).get("total_files", 0)
            }
            workflow.logger.info(f"✓ Workflow completed successfully: {workflow_id}")

            return results

        except Exception as e:
            workflow.logger.error(f"Workflow failed: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            results["steps"].append({
                "step": "error",
                "status": "failed",
                "error": str(e)
            })
            raise
