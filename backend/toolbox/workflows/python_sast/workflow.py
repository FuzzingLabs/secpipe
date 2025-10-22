"""
Python SAST Workflow - Temporal Version

Static Application Security Testing for Python projects using multiple tools.
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
class PythonSastWorkflow:
    """
    Python Static Application Security Testing workflow.

    This workflow:
    1. Downloads target from MinIO
    2. Runs dependency scanning (pip-audit for CVEs)
    3. Runs security linting (Bandit for security issues)
    4. Runs type checking (Mypy for type safety)
    5. Generates a SARIF report with all findings
    6. Uploads results to MinIO
    7. Cleans up cache
    """

    @workflow.run
    async def run(
        self,
        target_id: str,
        dependency_config: Optional[Dict[str, Any]] = None,
        bandit_config: Optional[Dict[str, Any]] = None,
        mypy_config: Optional[Dict[str, Any]] = None,
        reporter_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of the uploaded target in MinIO
            dependency_config: Configuration for dependency scanner
            bandit_config: Configuration for Bandit analyzer
            mypy_config: Configuration for Mypy analyzer
            reporter_config: Configuration for SARIF reporter

        Returns:
            Dictionary containing SARIF report and summary
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting PythonSASTWorkflow "
            f"(workflow_id={workflow_id}, target_id={target_id})"
        )

        # Default configurations
        if not dependency_config:
            dependency_config = {
                "dependency_files": [],  # Auto-discover
                "ignore_vulns": []
            }

        if not bandit_config:
            bandit_config = {
                "severity_level": "low",
                "confidence_level": "medium",
                "exclude_tests": True,
                "skip_ids": []
            }

        if not mypy_config:
            mypy_config = {
                "strict_mode": False,
                "ignore_missing_imports": True,
                "follow_imports": "silent"
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

            # Step 2: Dependency scanning (pip-audit)
            workflow.logger.info("Step 2: Scanning dependencies for vulnerabilities")
            dependency_results = await workflow.execute_activity(
                "scan_dependencies",
                args=[target_path, dependency_config],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )
            results["steps"].append({
                "step": "dependency_scanning",
                "status": "success",
                "vulnerabilities": dependency_results.get("summary", {}).get("total_vulnerabilities", 0)
            })
            workflow.logger.info(
                f"✓ Dependency scanning completed: "
                f"{dependency_results.get('summary', {}).get('total_vulnerabilities', 0)} vulnerabilities"
            )

            # Step 3: Security linting (Bandit)
            workflow.logger.info("Step 3: Analyzing security issues with Bandit")
            bandit_results = await workflow.execute_activity(
                "analyze_with_bandit",
                args=[target_path, bandit_config],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )
            results["steps"].append({
                "step": "bandit_analysis",
                "status": "success",
                "issues": bandit_results.get("summary", {}).get("total_issues", 0)
            })
            workflow.logger.info(
                f"✓ Bandit analysis completed: "
                f"{bandit_results.get('summary', {}).get('total_issues', 0)} security issues"
            )

            # Step 4: Type checking (Mypy)
            workflow.logger.info("Step 4: Type checking with Mypy")
            mypy_results = await workflow.execute_activity(
                "analyze_with_mypy",
                args=[target_path, mypy_config],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )
            results["steps"].append({
                "step": "mypy_analysis",
                "status": "success",
                "type_errors": mypy_results.get("summary", {}).get("total_errors", 0)
            })
            workflow.logger.info(
                f"✓ Mypy analysis completed: "
                f"{mypy_results.get('summary', {}).get('total_errors', 0)} type errors"
            )

            # Step 5: Generate SARIF report
            workflow.logger.info("Step 5: Generating SARIF report")
            sarif_report = await workflow.execute_activity(
                "generate_python_sast_sarif",
                args=[dependency_results, bandit_results, mypy_results, reporter_config, target_path],
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

            # Step 6: Upload results to MinIO
            workflow.logger.info("Step 6: Uploading results")
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

            # Step 7: Cleanup cache
            workflow.logger.info("Step 7: Cleaning up cache")
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
                "vulnerabilities": dependency_results.get("summary", {}).get("total_vulnerabilities", 0),
                "security_issues": bandit_results.get("summary", {}).get("total_issues", 0),
                "type_errors": mypy_results.get("summary", {}).get("total_errors", 0)
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
