"""
LLM Analysis Workflow - Temporal Version

Uses AI/LLM to analyze code for security issues.
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

# Import for type hints (will be executed by worker)
with workflow.unsafe.imports_passed_through():
    import logging

logger = logging.getLogger(__name__)


@workflow.defn
class LlmAnalysisWorkflow:
    """
    Analyze code using AI/LLM for security vulnerabilities.

    User workflow:
    1. User runs: ff workflow run llm_analysis .
    2. CLI uploads project to MinIO
    3. Worker downloads project
    4. Worker calls LLM analyzer module
    5. LLM analyzes code files and reports findings
    6. Results returned in SARIF format
    """

    @workflow.run
    async def run(
        self,
        target_id: str,  # MinIO UUID of uploaded user code
        agent_url: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_provider: Optional[str] = None,
        file_patterns: Optional[list] = None,
        max_files: Optional[int] = None,
        max_file_size: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of the uploaded target in MinIO
            agent_url: A2A agent endpoint URL
            llm_model: LLM model to use
            llm_provider: LLM provider
            file_patterns: File patterns to analyze
            max_files: Maximum number of files to analyze
            max_file_size: Maximum file size in bytes
            timeout: Timeout per file in seconds

        Returns:
            Dictionary containing findings and summary
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting LLMAnalysisWorkflow "
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

            # Step 2: Run LLM analysis
            workflow.logger.info("Step 2: Analyzing code with LLM")

            # Build analyzer config
            analyzer_config = {}
            if agent_url:
                analyzer_config["agent_url"] = agent_url
            if llm_model:
                analyzer_config["llm_model"] = llm_model
            if llm_provider:
                analyzer_config["llm_provider"] = llm_provider
            if file_patterns:
                analyzer_config["file_patterns"] = file_patterns
            if max_files is not None:
                analyzer_config["max_files"] = max_files
            if max_file_size is not None:
                analyzer_config["max_file_size"] = max_file_size
            if timeout is not None:
                analyzer_config["timeout"] = timeout

            analysis_results = await workflow.execute_activity(
                "analyze_with_llm",
                args=[target_path, analyzer_config],
                start_to_close_timeout=timedelta(minutes=30),  # LLM calls can be slow
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=2
                )
            )

            findings = analysis_results.get("findings", [])
            summary = analysis_results.get("summary", {})

            results["steps"].append({
                "step": "llm_analysis",
                "status": "success",
                "files_analyzed": summary.get("files_analyzed", 0),
                "findings_count": len(findings)
            })

            workflow.logger.info(
                f"✓ LLM analysis completed: "
                f"{summary.get('files_analyzed', 0)} files, "
                f"{len(findings)} findings"
            )

            # Step 3: Generate SARIF report
            workflow.logger.info("Step 3: Generating SARIF report")

            sarif_report = await workflow.execute_activity(
                "llm_generate_sarif",
                args=[findings, {
                    "tool_name": "llm-analyzer",
                    "tool_version": "1.0.0",
                    "run_id": run_id
                }],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )

            results["steps"].append({
                "step": "sarif_generation",
                "status": "success",
                "results_count": len(sarif_report.get("runs", [{}])[0].get("results", []))
            })

            workflow.logger.info(
                f"✓ SARIF report generated: "
                f"{len(sarif_report.get('runs', [{}])[0].get('results', []))} results"
            )

            # Step 4: Upload results to MinIO
            workflow.logger.info("Step 4: Uploading results to MinIO")

            # Upload SARIF report
            if sarif_report:
                results_url = await workflow.execute_activity(
                    "upload_results",
                    args=[run_id, sarif_report],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(seconds=30),
                        maximum_attempts=3
                    )
                )
                results["results_url"] = results_url
                workflow.logger.info(f"✓ Results uploaded to: {results_url}")

            # Step 5: Cleanup cache
            workflow.logger.info("Step 5: Cleaning up cache")
            await workflow.execute_activity(
                "cleanup_cache",
                args=[target_id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    maximum_attempts=2
                )
            )
            workflow.logger.info("✓ Cache cleaned up")

            # Mark workflow as successful
            results["status"] = "success"
            results["sarif"] = sarif_report
            results["summary"] = summary
            results["findings"] = findings

            workflow.logger.info(
                f"✅ LLMAnalysisWorkflow completed successfully: "
                f"{len(findings)} findings"
            )

        except Exception as e:
            workflow.logger.error(f"❌ Workflow failed: {e}")
            results["status"] = "failed"
            results["error"] = str(e)
            raise

        return results
