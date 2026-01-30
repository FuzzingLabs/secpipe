"""
OSS-Fuzz Campaign Workflow - Temporal Version

Generic workflow for running OSS-Fuzz campaigns using Google's infrastructure.
Automatically reads project configuration from OSS-Fuzz project.yaml files.
"""

import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import for type hints (will be executed by worker)
with workflow.unsafe.imports_passed_through():
    import logging

logger = logging.getLogger(__name__)


@workflow.defn
class OssfuzzCampaignWorkflow:
    """
    Generic OSS-Fuzz fuzzing campaign workflow.

    User workflow:
    1. User runs: ff workflow run ossfuzz_campaign . project_name=curl
    2. Worker loads project config from OSS-Fuzz repo
    3. Worker builds project using OSS-Fuzz's build system
    4. Worker runs fuzzing with engines from project.yaml
    5. Crashes and corpus reported as findings
    """

    @workflow.run
    async def run(
        self,
        target_id: str,  # Required by FuzzForge (not used, OSS-Fuzz downloads from Google)
        project_name: str,  # Required: OSS-Fuzz project name (e.g., "curl", "sqlite3")
        campaign_duration_hours: int = 1,
        override_engine: Optional[str] = None,  # Override engine from project.yaml
        override_sanitizer: Optional[str] = None,  # Override sanitizer from project.yaml
        max_iterations: Optional[int] = None  # Optional: limit fuzzing iterations
    ) -> Dict[str, Any]:
        """
        Main workflow execution.

        Args:
            target_id: UUID of uploaded target (not used, required by FuzzForge)
            project_name: Name of OSS-Fuzz project (e.g., "curl", "sqlite3", "libxml2")
            campaign_duration_hours: How many hours to fuzz (default: 1)
            override_engine: Override fuzzing engine from project.yaml
            override_sanitizer: Override sanitizer from project.yaml
            max_iterations: Optional limit on fuzzing iterations

        Returns:
            Dictionary containing crashes, stats, and SARIF report
        """
        workflow_id = workflow.info().workflow_id

        workflow.logger.info(
            f"Starting OSS-Fuzz Campaign for project '{project_name}' "
            f"(workflow_id={workflow_id}, duration={campaign_duration_hours}h)"
        )

        results = {
            "workflow_id": workflow_id,
            "project_name": project_name,
            "status": "running",
            "steps": []
        }

        try:
            # Step 1: Load OSS-Fuzz project configuration
            workflow.logger.info(f"Step 1: Loading project config for '{project_name}'")
            project_config = await workflow.execute_activity(
                "load_ossfuzz_project",
                args=[project_name],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3
                )
            )

            results["steps"].append({
                "step": "load_config",
                "status": "success",
                "language": project_config.get("language"),
                "engines": project_config.get("fuzzing_engines", []),
                "sanitizers": project_config.get("sanitizers", [])
            })

            workflow.logger.info(
                f"✓ Loaded config: language={project_config.get('language')}, "
                f"engines={project_config.get('fuzzing_engines')}"
            )

            # Step 2: Build project using OSS-Fuzz infrastructure
            workflow.logger.info(f"Step 2: Building project '{project_name}'")

            build_result = await workflow.execute_activity(
                "build_ossfuzz_project",
                args=[
                    project_name,
                    project_config,
                    override_sanitizer,
                    override_engine
                ],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=60),
                    maximum_attempts=2
                )
            )

            results["steps"].append({
                "step": "build_project",
                "status": "success",
                "fuzz_targets": len(build_result.get("fuzz_targets", [])),
                "sanitizer": build_result.get("sanitizer_used"),
                "engine": build_result.get("engine_used")
            })

            workflow.logger.info(
                f"✓ Build completed: {len(build_result.get('fuzz_targets', []))} fuzz targets found"
            )

            if not build_result.get("fuzz_targets"):
                raise Exception(f"No fuzz targets found for project {project_name}")

            # Step 3: Run fuzzing on discovered targets
            workflow.logger.info(f"Step 3: Fuzzing {len(build_result['fuzz_targets'])} targets")

            # Determine which engine to use
            engine_to_use = override_engine if override_engine else build_result["engine_used"]
            duration_seconds = campaign_duration_hours * 3600

            # Fuzz each target (in parallel if multiple targets)
            fuzz_futures = []
            for target_path in build_result["fuzz_targets"]:
                future = workflow.execute_activity(
                    "fuzz_target",
                    args=[target_path, engine_to_use, duration_seconds, None, None],
                    start_to_close_timeout=timedelta(seconds=duration_seconds + 300),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_interval=timedelta(seconds=60),
                        maximum_attempts=1  # Fuzzing shouldn't retry
                    )
                )
                fuzz_futures.append(future)

            # Wait for all fuzzing to complete
            fuzz_results = await asyncio.gather(*fuzz_futures, return_exceptions=True)

            # Aggregate results
            total_execs = 0
            total_crashes = 0
            all_crashes = []

            for i, result in enumerate(fuzz_results):
                if isinstance(result, Exception):
                    workflow.logger.error(f"Fuzzing failed for target {i}: {result}")
                    continue

                total_execs += result.get("total_executions", 0)
                total_crashes += result.get("crashes", 0)
                all_crashes.extend(result.get("crash_files", []))

            results["steps"].append({
                "step": "fuzzing",
                "status": "success",
                "total_executions": total_execs,
                "crashes_found": total_crashes,
                "targets_fuzzed": len(build_result["fuzz_targets"])
            })

            workflow.logger.info(
                f"✓ Fuzzing completed: {total_execs} executions, {total_crashes} crashes"
            )

            # Step 4: Generate SARIF report
            workflow.logger.info("Step 4: Generating SARIF report")

            # TODO: Implement crash minimization and SARIF generation
            # For now, return raw results

            results["status"] = "success"
            results["summary"] = {
                "project": project_name,
                "total_executions": total_execs,
                "crashes_found": total_crashes,
                "unique_crashes": len(set(all_crashes)),
                "duration_hours": campaign_duration_hours,
                "engine_used": engine_to_use,
                "sanitizer_used": build_result.get("sanitizer_used")
            }
            results["crashes"] = all_crashes[:100]  # Limit to first 100 crashes

            workflow.logger.info(
                f"✓ Campaign completed: {project_name} - "
                f"{total_execs} execs, {total_crashes} crashes"
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
