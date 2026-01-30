"""
Atheris Fuzzing Workflow - Temporal Version

Fuzzes user-provided Python code using Atheris with real-time monitoring.
"""

from datetime import timedelta
from typing import Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import for type hints (will be executed by worker)
with workflow.unsafe.imports_passed_through():
    import logging

logger = logging.getLogger(__name__)


@workflow.defn
class AtherisFuzzingWorkflow:
    """
    Fuzz Python code using Atheris.

    User workflow:
    1. User runs: ff workflow run atheris_fuzzing .
    2. CLI uploads project to MinIO
    3. Worker downloads project
    4. Worker fuzzes TestOneInput() function
    5. Crashes reported as findings
    """

    @workflow.run
    async def run(
        self,
        target_id: str,  # MinIO UUID of uploaded user code
        target_file: Optional[str] = None,  # Optional: specific file to fuzz
        max_iterations: int = 1000000,
        timeout_seconds: int = 1800  # 30 minutes default for fuzzing
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of the uploaded target in MinIO
            target_file: Optional specific Python file with TestOneInput() (auto-discovered if None)
            max_iterations: Maximum fuzzing iterations
            timeout_seconds: Fuzzing timeout in seconds

        Returns:
            Dictionary containing findings and summary
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting AtherisFuzzingWorkflow "
            f"(workflow_id={workflow_id}, target_id={target_id}, "
            f"target_file={target_file or 'auto-discover'}, max_iterations={max_iterations}, "
            f"timeout_seconds={timeout_seconds})"
        )

        results = {
            "workflow_id": workflow_id,
            "target_id": target_id,
            "status": "running",
            "steps": []
        }

        try:
            # Get run ID for workspace isolation
            run_id = workflow.info().run_id

            # Step 1: Download user's project from MinIO
            workflow.logger.info("Step 1: Downloading user code from MinIO")
            target_path = await workflow.execute_activity(
                "get_target",
                args=[target_id, run_id, "isolated"],  # target_id, run_id, workspace_isolation
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
            workflow.logger.info(f"✓ User code downloaded to: {target_path}")

            # Step 2: Run Atheris fuzzing
            workflow.logger.info("Step 2: Running Atheris fuzzing")

            # Use defaults if parameters are None
            actual_max_iterations = max_iterations if max_iterations is not None else 1000000
            actual_timeout_seconds = timeout_seconds if timeout_seconds is not None else 1800

            fuzz_config = {
                "target_file": target_file,
                "max_iterations": actual_max_iterations,
                "timeout_seconds": actual_timeout_seconds
            }

            fuzz_results = await workflow.execute_activity(
                "fuzz_with_atheris",
                args=[target_path, fuzz_config],
                start_to_close_timeout=timedelta(seconds=actual_timeout_seconds + 60),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=1  # Fuzzing shouldn't retry
                )
            )

            results["steps"].append({
                "step": "fuzzing",
                "status": "success",
                "executions": fuzz_results.get("summary", {}).get("total_executions", 0),
                "crashes": fuzz_results.get("summary", {}).get("crashes_found", 0)
            })
            workflow.logger.info(
                f"✓ Fuzzing completed: "
                f"{fuzz_results.get('summary', {}).get('total_executions', 0)} executions, "
                f"{fuzz_results.get('summary', {}).get('crashes_found', 0)} crashes"
            )

            # Step 3: Upload results to MinIO
            workflow.logger.info("Step 3: Uploading results")
            try:
                results_url = await workflow.execute_activity(
                    "upload_results",
                    args=[workflow_id, fuzz_results, "json"],
                    start_to_close_timeout=timedelta(minutes=2)
                )
                results["results_url"] = results_url
                workflow.logger.info(f"✓ Results uploaded to: {results_url}")
            except Exception as e:
                workflow.logger.warning(f"Failed to upload results: {e}")
                results["results_url"] = None

            # Step 4: Cleanup cache
            workflow.logger.info("Step 4: Cleaning up cache")
            try:
                await workflow.execute_activity(
                    "cleanup_cache",
                    args=[target_path, "isolated"],  # target_path, workspace_isolation
                    start_to_close_timeout=timedelta(minutes=1)
                )
                workflow.logger.info("✓ Cache cleaned up")
            except Exception as e:
                workflow.logger.warning(f"Cache cleanup failed: {e}")

            # Mark workflow as successful
            results["status"] = "success"
            results["findings"] = fuzz_results.get("findings", [])
            results["summary"] = fuzz_results.get("summary", {})
            results["sarif"] = fuzz_results.get("sarif") or {}
            workflow.logger.info(
                f"✓ Workflow completed successfully: {workflow_id} "
                f"({results['summary'].get('crashes_found', 0)} crashes found)"
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
