"""
Gitleaks Detection Workflow - Temporal Version

Scans code for secrets and credentials using Gitleaks.
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
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import for type hints (will be executed by worker)
with workflow.unsafe.imports_passed_through():
    import logging

logger = logging.getLogger(__name__)


@workflow.defn
class GitleaksDetectionWorkflow:
    """
    Scan code for secrets using Gitleaks.

    User workflow:
    1. User runs: ff workflow run gitleaks_detection .
    2. CLI uploads project to MinIO
    3. Worker downloads project
    4. Worker runs Gitleaks
    5. Secrets reported as findings in SARIF format
    """

    @workflow.run
    async def run(
        self,
        target_id: str,  # MinIO UUID of uploaded user code
        scan_mode: str = "detect",
        redact: bool = True,
        no_git: bool = True
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of the uploaded target in MinIO
            scan_mode: Scan mode ('detect' or 'protect')
            redact: Redact secrets in output
            no_git: Scan files without Git context

        Returns:
            Dictionary containing findings and summary
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting GitleaksDetectionWorkflow "
            f"(workflow_id={workflow_id}, target_id={target_id}, scan_mode={scan_mode})"
        )

        results = {
            "workflow_id": workflow_id,
            "target_id": target_id,
            "status": "running",
            "steps": [],
            "findings": []
        }

        try:
            # Get run ID for workspace isolation
            run_id = workflow.info().run_id

            # Step 1: Download user's project from MinIO
            workflow.logger.info("Step 1: Downloading user code from MinIO")
            target_path = await workflow.execute_activity(
                "get_target",
                args=[target_id, run_id, "shared"],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )
            results["steps"].append({
                "step": "download",
                "status": "success",
                "target_path": target_path
            })
            workflow.logger.info(f"✓ Target downloaded to: {target_path}")

            # Step 2: Run Gitleaks
            workflow.logger.info("Step 2: Scanning with Gitleaks")

            scan_config = {
                "scan_mode": scan_mode,
                "redact": redact,
                "no_git": no_git
            }

            scan_results = await workflow.execute_activity(
                "scan_with_gitleaks",
                args=[target_path, scan_config],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )

            results["steps"].append({
                "step": "gitleaks_scan",
                "status": "success",
                "leaks_found": scan_results.get("summary", {}).get("total_leaks", 0)
            })
            workflow.logger.info(
                f"✓ Gitleaks scan completed: "
                f"{scan_results.get('summary', {}).get('total_leaks', 0)} leaks found"
            )

            # Step 3: Generate SARIF report
            workflow.logger.info("Step 3: Generating SARIF report")
            sarif_report = await workflow.execute_activity(
                "gitleaks_generate_sarif",
                args=[scan_results.get("findings", []), {"tool_name": "gitleaks", "tool_version": "8.18.0"}],
                start_to_close_timeout=timedelta(minutes=2)
            )

            # Step 4: Upload results to MinIO
            workflow.logger.info("Step 4: Uploading results")
            try:
                results_url = await workflow.execute_activity(
                    "upload_results",
                    args=[workflow_id, scan_results, "json"],
                    start_to_close_timeout=timedelta(minutes=2)
                )
                results["results_url"] = results_url
                workflow.logger.info(f"✓ Results uploaded to: {results_url}")
            except Exception as e:
                workflow.logger.warning(f"Failed to upload results: {e}")
                results["results_url"] = None

            # Step 5: Cleanup cache
            workflow.logger.info("Step 5: Cleaning up cache")
            try:
                await workflow.execute_activity(
                    "cleanup_cache",
                    args=[target_path, "shared"],
                    start_to_close_timeout=timedelta(minutes=1)
                )
                workflow.logger.info("✓ Cache cleaned up")
            except Exception as e:
                workflow.logger.warning(f"Cache cleanup failed: {e}")

            # Mark workflow as successful
            results["status"] = "success"
            results["findings"] = scan_results.get("findings", [])
            results["summary"] = scan_results.get("summary", {})
            results["sarif"] = sarif_report or {}
            workflow.logger.info(
                f"✓ Workflow completed successfully: {workflow_id} "
                f"({results['summary'].get('total_leaks', 0)} leaks found)"
            )

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
