"""
Cargo Fuzzing Workflow Activities

Activities specific to the cargo-fuzz fuzzing workflow.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import os

import httpx
from temporalio import activity

# Configure logging
logger = logging.getLogger(__name__)

# Add toolbox to path for module imports
sys.path.insert(0, '/app/toolbox')


@activity.defn(name="fuzz_with_cargo")
async def fuzz_activity(workspace_path: str, config: dict) -> dict:
    """
    Fuzzing activity using the CargoFuzzer module on user code.

    This activity:
    1. Imports the reusable CargoFuzzer module
    2. Sets up real-time stats callback
    3. Executes fuzzing on user's fuzz_target!() functions
    4. Returns findings as ModuleResult

    Args:
        workspace_path: Path to the workspace directory (user's uploaded Rust project)
        config: Fuzzer configuration (target_name, max_iterations, timeout_seconds, sanitizer)

    Returns:
        Fuzzer results dictionary (findings, summary, metadata)
    """
    logger.info(f"Activity: fuzz_with_cargo (workspace={workspace_path})")

    try:
        # Import reusable CargoFuzzer module
        from modules.fuzzer import CargoFuzzer

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        # Get activity info for real-time stats
        info = activity.info()
        run_id = info.workflow_id

        # Define stats callback for real-time monitoring
        async def stats_callback(stats_data: Dict[str, Any]):
            """Callback for live fuzzing statistics"""
            try:
                # Prepare stats payload for backend
                coverage_value = stats_data.get("coverage", 0)

                stats_payload = {
                    "run_id": run_id,
                    "workflow": "cargo_fuzzing",
                    "executions": stats_data.get("total_execs", 0),
                    "executions_per_sec": stats_data.get("execs_per_sec", 0.0),
                    "crashes": stats_data.get("crashes", 0),
                    "unique_crashes": stats_data.get("crashes", 0),
                    "coverage": coverage_value,
                    "corpus_size": stats_data.get("corpus_size", 0),
                    "elapsed_time": stats_data.get("elapsed_time", 0),
                    "last_crash_time": None
                }

                # POST stats to backend API for real-time monitoring
                backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
                async with httpx.AsyncClient(timeout=5.0) as client:
                    try:
                        await client.post(
                            f"{backend_url}/fuzzing/{run_id}/stats",
                            json=stats_payload
                        )
                    except Exception as http_err:
                        logger.debug(f"Failed to post stats to backend: {http_err}")

                # Also log for debugging
                logger.info("LIVE_STATS", extra={
                    "stats_type": "fuzzing_live_update",
                    "workflow_type": "cargo_fuzzing",
                    "run_id": run_id,
                    "executions": stats_data.get("total_execs", 0),
                    "executions_per_sec": stats_data.get("execs_per_sec", 0.0),
                    "crashes": stats_data.get("crashes", 0),
                    "corpus_size": stats_data.get("corpus_size", 0),
                    "coverage": stats_data.get("coverage", 0.0),
                    "elapsed_time": stats_data.get("elapsed_time", 0),
                    "timestamp": datetime.utcnow().isoformat()
                })

            except Exception as e:
                logger.error(f"Stats callback error: {e}")

        # Initialize CargoFuzzer module
        fuzzer = CargoFuzzer()

        # Execute fuzzing with stats callback
        module_result = await fuzzer.execute(
            config=config,
            workspace=workspace,
            stats_callback=stats_callback
        )

        # Convert ModuleResult to dictionary
        result_dict = {
            "findings": [],
            "summary": module_result.summary,
            "metadata": module_result.metadata,
            "status": module_result.status,
            "error": module_result.error
        }

        # Convert findings to dict format
        for finding in module_result.findings:
            finding_dict = {
                "id": finding.id,
                "title": finding.title,
                "description": finding.description,
                "severity": finding.severity,
                "category": finding.category,
                "file_path": finding.file_path,
                "line_start": finding.line_start,
                "line_end": finding.line_end,
                "code_snippet": finding.code_snippet,
                "recommendation": finding.recommendation,
                "metadata": finding.metadata
            }
            result_dict["findings"].append(finding_dict)

        # Generate SARIF report from findings
        if module_result.findings:
            # Convert findings to SARIF format
            severity_map = {
                "critical": "error",
                "high": "error",
                "medium": "warning",
                "low": "note",
                "info": "note"
            }

            results = []
            for finding in module_result.findings:
                result = {
                    "ruleId": finding.metadata.get("rule_id", finding.category),
                    "level": severity_map.get(finding.severity, "warning"),
                    "message": {"text": finding.description},
                    "locations": []
                }

                if finding.file_path:
                    location = {
                        "physicalLocation": {
                            "artifactLocation": {"uri": finding.file_path},
                            "region": {
                                "startLine": finding.line_start or 1,
                                "endLine": finding.line_end or finding.line_start or 1
                            }
                        }
                    }
                    result["locations"].append(location)

                results.append(result)

            result_dict["sarif"] = {
                "version": "2.1.0",
                "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                "runs": [{
                    "tool": {
                        "driver": {
                            "name": "cargo-fuzz",
                            "version": "0.11.2"
                        }
                    },
                    "results": results
                }]
            }
        else:
            result_dict["sarif"] = {
                "version": "2.1.0",
                "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                "runs": []
            }

        logger.info(
            f"Fuzzing activity completed: {len(module_result.findings)} crashes found, "
            f"{module_result.summary.get('total_executions', 0)} executions"
        )

        return result_dict

    except Exception as e:
        logger.error(f"Fuzzing activity failed: {e}", exc_info=True)
        raise
