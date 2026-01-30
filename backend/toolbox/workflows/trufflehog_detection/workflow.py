"""TruffleHog Detection Workflow"""

from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn
class TrufflehogDetectionWorkflow:
    """Scan code for secrets using TruffleHog."""

    @workflow.run
    async def run(self, target_id: str, verify: bool = False, concurrency: int = 10) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        run_id = workflow.info().run_id

        workflow.logger.info(
            f"Starting TrufflehogDetectionWorkflow "
            f"(workflow_id={workflow_id}, target_id={target_id}, verify={verify})"
        )

        results = {"workflow_id": workflow_id, "status": "running", "findings": []}

        try:
            # Step 1: Download target
            workflow.logger.info("Step 1: Downloading target from MinIO")
            target_path = await workflow.execute_activity(
                "get_target", args=[target_id, run_id, "shared"],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )
            workflow.logger.info(f"✓ Target downloaded to: {target_path}")

            # Step 2: Scan with TruffleHog
            workflow.logger.info("Step 2: Scanning with TruffleHog")
            scan_results = await workflow.execute_activity(
                "scan_with_trufflehog",
                args=[target_path, {"verify": verify, "concurrency": concurrency}],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )
            workflow.logger.info(
                f"✓ TruffleHog scan completed: "
                f"{scan_results.get('summary', {}).get('total_secrets', 0)} secrets found"
            )

            # Step 3: Generate SARIF report
            workflow.logger.info("Step 3: Generating SARIF report")
            sarif_report = await workflow.execute_activity(
                "trufflehog_generate_sarif",
                args=[scan_results.get("findings", []), {"tool_name": "trufflehog", "tool_version": "3.63.2"}],
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

            # Step 5: Cleanup
            workflow.logger.info("Step 5: Cleaning up cache")
            try:
                await workflow.execute_activity(
                    "cleanup_cache", args=[target_path, "shared"],
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
                f"({results['summary'].get('total_secrets', 0)} secrets found)"
            )

            return results

        except Exception as e:
            workflow.logger.error(f"Workflow failed: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            raise
