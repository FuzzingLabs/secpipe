"""LLM Secret Detection Workflow"""

from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn
class LlmSecretDetectionWorkflow:
    """Scan code for secrets using LLM AI."""

    @workflow.run
    async def run(
        self,
        target_id: str,
        agent_url: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_provider: Optional[str] = None,
        max_files: Optional[int] = None,
        max_file_size: Optional[int] = None,
        timeout: Optional[int] = None,
        file_patterns: Optional[list] = None
    ) -> Dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        run_id = workflow.info().run_id

        workflow.logger.info(
            f"Starting LLM Secret Detection Workflow "
            f"(workflow_id={workflow_id}, target_id={target_id}, model={llm_model})"
        )

        results = {
            "workflow_id": workflow_id,
            "target_id": target_id,
            "status": "running",
            "steps": [],
            "findings": []
        }

        try:
            # Step 1: Download target from MinIO
            workflow.logger.info("Step 1: Downloading target from MinIO")
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

            # Step 2: Scan with LLM
            workflow.logger.info("Step 2: Scanning with LLM")
            config = {}
            if agent_url:
                config["agent_url"] = agent_url
            if llm_model:
                config["llm_model"] = llm_model
            if llm_provider:
                config["llm_provider"] = llm_provider
            if max_files:
                config["max_files"] = max_files
            if max_file_size:
                config["max_file_size"] = max_file_size
            if timeout:
                config["timeout"] = timeout
            if file_patterns:
                config["file_patterns"] = file_patterns

            scan_results = await workflow.execute_activity(
                "scan_with_llm",
                args=[target_path, config],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )

            findings_count = len(scan_results.get("findings", []))
            results["steps"].append({
                "step": "llm_scan",
                "status": "success",
                "secrets_found": findings_count
            })
            workflow.logger.info(f"✓ LLM scan completed: {findings_count} secrets found")

            # Step 3: Generate SARIF report
            workflow.logger.info("Step 3: Generating SARIF report")
            sarif_report = await workflow.execute_activity(
                "llm_generate_sarif",  # Use shared LLM SARIF activity
                args=[
                    scan_results.get("findings", []),
                    {
                        "tool_name": f"llm-secret-detector ({llm_model or 'gpt-4o-mini'})",
                        "tool_version": "1.0.0"
                    }
                ],
                start_to_close_timeout=timedelta(minutes=2)
            )
            workflow.logger.info("✓ SARIF report generated")

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
                f"({findings_count} secrets found)"
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
