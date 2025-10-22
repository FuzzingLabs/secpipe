#!/usr/bin/env python3
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

"""
Batch analysis example.

This example demonstrates how to:
1. Analyze multiple projects or targets
2. Run different workflows on the same target
3. Collect and compare results
4. Generate summary reports
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import time

from fuzzforge_sdk import (
    FuzzForgeClient
)
from fuzzforge_sdk.utils import (
    create_workflow_submission,
    format_sarif_summary,
    count_sarif_severity_levels,
    save_sarif_to_file,
    get_project_files
)


class BatchAnalyzer:
    """Batch analysis manager."""

    def __init__(self, client: FuzzForgeClient):
        self.client = client
        self.results: List[Dict[str, Any]] = []

    async def analyze_project(
        self,
        project_path: Path,
        workflows: List[str],
        output_dir: Path
    ) -> Dict[str, Any]:
        """
        Analyze a single project with multiple workflows.

        Args:
            project_path: Path to project to analyze
            workflows: List of workflow names to run
            output_dir: Directory to save results

        Returns:
            Analysis results summary
        """
        print(f"\n📁 Analyzing project: {project_path.name}")
        print(f"   Path: {project_path}")
        print(f"   Workflows: {', '.join(workflows)}")

        project_results = {
            "project_name": project_path.name,
            "project_path": str(project_path),
            "workflows": {},
            "summary": {},
            "start_time": time.time()
        }

        # Get project info
        try:
            files = get_project_files(project_path)
            project_results["file_count"] = len(files)
            project_results["total_size"] = sum(f.stat().st_size for f in files if f.exists())
            print(f"   Files: {len(files)}")
        except Exception as e:
            print(f"   ⚠️  Could not analyze project structure: {e}")
            project_results["file_count"] = 0
            project_results["total_size"] = 0

        # Create project output directory
        project_output_dir = output_dir / project_path.name
        project_output_dir.mkdir(parents=True, exist_ok=True)

        # Run each workflow
        for workflow_name in workflows:
            try:
                workflow_result = await self._run_workflow_on_project(
                    project_path,
                    workflow_name,
                    project_output_dir
                )
                project_results["workflows"][workflow_name] = workflow_result

            except Exception as e:
                print(f"   ❌ Failed to run {workflow_name}: {e}")
                project_results["workflows"][workflow_name] = {
                    "status": "failed",
                    "error": str(e)
                }

        # Calculate summary
        project_results["end_time"] = time.time()
        project_results["duration"] = project_results["end_time"] - project_results["start_time"]
        project_results["summary"] = self._calculate_project_summary(project_results)

        # Save project summary
        summary_file = project_output_dir / "analysis_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(project_results, f, indent=2, default=str)

        print(f"   ✅ Analysis complete in {project_results['duration']:.1f}s")
        return project_results

    async def _run_workflow_on_project(
        self,
        project_path: Path,
        workflow_name: str,
        output_dir: Path
    ) -> Dict[str, Any]:
        """Run a single workflow on a project."""
        print(f"      🔄 Running {workflow_name}...")

        # Get workflow metadata for better parameter selection
        try:
            metadata = await self.client.aget_workflow_metadata(workflow_name)

            # Determine appropriate timeout based on workflow type
            if "fuzzing" in metadata.tags:
                timeout = 1800  # 30 minutes for fuzzing
            elif "dynamic" in metadata.tags:
                timeout = 900   # 15 minutes for dynamic analysis
            else:
                timeout = 300   # 5 minutes for static analysis

        except Exception:
            # Fallback settings
            timeout = 600

        # Create submission
        submission = create_workflow_submission(
            target_path=project_path,
            timeout=timeout
        )

        # Submit workflow
        start_time = time.time()
        response = await self.client.asubmit_workflow(workflow_name, submission)

        # Wait for completion
        try:
            final_status = await self.client.await_for_completion(
                response.run_id,
                poll_interval=10.0,
                timeout=float(timeout + 300)  # Add buffer for completion timeout
            )

            end_time = time.time()
            duration = end_time - start_time

            # Get findings if successful
            findings = None
            if final_status.is_completed and not final_status.is_failed:
                try:
                    findings = await self.client.aget_run_findings(response.run_id)

                    # Save SARIF results
                    sarif_file = output_dir / f"{workflow_name}_results.sarif.json"
                    save_sarif_to_file(findings.sarif, sarif_file)

                    print(f"      ✅ {workflow_name} completed: {format_sarif_summary(findings.sarif)}")

                except Exception as e:
                    print(f"      ⚠️  Could not retrieve findings for {workflow_name}: {e}")

            result = {
                "status": "completed" if final_status.is_completed else "failed",
                "run_id": response.run_id,
                "duration": duration,
                "final_status": final_status.status,
                "findings_summary": format_sarif_summary(findings.sarif) if findings else None,
                "severity_counts": count_sarif_severity_levels(findings.sarif) if findings else None
            }

            return result

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"      ❌ {workflow_name} failed after {duration:.1f}s: {e}")

            return {
                "status": "failed",
                "run_id": response.run_id,
                "duration": duration,
                "error": str(e)
            }

    def _calculate_project_summary(self, project_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics for a project analysis."""
        workflows = project_results["workflows"]

        total_findings = {}
        successful_workflows = 0
        failed_workflows = 0

        for workflow_name, workflow_result in workflows.items():
            if workflow_result["status"] == "completed":
                successful_workflows += 1

                # Aggregate severity counts
                severity_counts = workflow_result.get("severity_counts", {})
                for severity, count in severity_counts.items():
                    total_findings[severity] = total_findings.get(severity, 0) + count

            else:
                failed_workflows += 1

        return {
            "successful_workflows": successful_workflows,
            "failed_workflows": failed_workflows,
            "total_workflows": len(workflows),
            "total_findings": total_findings,
            "total_issues": sum(total_findings.values())
        }


async def main():
    """Main batch analysis example."""
    # Configuration
    projects_to_analyze = [
        Path.cwd(),  # Current directory
        # Add more project paths here
        # Path("/path/to/project1"),
        # Path("/path/to/project2"),
    ]

    workflows_to_run = [
        # "static-analysis",
        # "security-scan",
        # "dependency-check",
        # Add actual workflow names from your FuzzForge instance
    ]

    output_base_dir = Path("./analysis_results")

    # Initialize client
    async with FuzzForgeClient(base_url="http://localhost:8000") as client:
        try:
            # Check API status
            print("🔗 Connecting to FuzzForge API...")
            status = await client.aget_api_status()
            print(f"✅ Connected to {status.name} v{status.version}")

            # Get available workflows
            available_workflows = await client.alist_workflows()
            available_names = [w.name for w in available_workflows]

            print(f"📋 Available workflows: {', '.join(available_names)}")

            # Filter requested workflows to only include available ones
            valid_workflows = [w for w in workflows_to_run if w in available_names]

            if not valid_workflows:
                print("⚠️  No valid workflows specified, using all available workflows")
                valid_workflows = available_names[:3]  # Limit to first 3 for demo

            print(f"🎯 Will run workflows: {', '.join(valid_workflows)}")

            # Create output directory
            output_base_dir.mkdir(parents=True, exist_ok=True)

            # Initialize batch analyzer
            analyzer = BatchAnalyzer(client)

            # Analyze each project
            batch_start_time = time.time()

            for project_path in projects_to_analyze:
                if not project_path.exists() or not project_path.is_dir():
                    print(f"⚠️  Skipping invalid project path: {project_path}")
                    continue

                project_result = await analyzer.analyze_project(
                    project_path,
                    valid_workflows,
                    output_base_dir
                )
                analyzer.results.append(project_result)

            batch_end_time = time.time()
            batch_duration = batch_end_time - batch_start_time

            # Generate batch summary report
            print("\n📊 Batch Analysis Complete!")
            print(f"   Total time: {batch_duration:.1f}s")
            print(f"   Projects analyzed: {len(analyzer.results)}")

            # Create overall summary
            batch_summary = {
                "start_time": batch_start_time,
                "end_time": batch_end_time,
                "duration": batch_duration,
                "projects": analyzer.results,
                "overall_stats": {}
            }

            # Calculate overall statistics
            total_successful = sum(r["summary"]["successful_workflows"] for r in analyzer.results)
            total_failed = sum(r["summary"]["failed_workflows"] for r in analyzer.results)
            total_issues = sum(r["summary"]["total_issues"] for r in analyzer.results)

            batch_summary["overall_stats"] = {
                "total_successful_runs": total_successful,
                "total_failed_runs": total_failed,
                "total_issues_found": total_issues
            }

            print(f"   Successful runs: {total_successful}")
            print(f"   Failed runs: {total_failed}")
            print(f"   Total issues found: {total_issues}")

            # Save batch summary
            batch_summary_file = output_base_dir / "batch_summary.json"
            with open(batch_summary_file, 'w') as f:
                json.dump(batch_summary, f, indent=2, default=str)

            print(f"\n💾 Results saved to: {output_base_dir}")
            print(f"   Batch summary: {batch_summary_file}")

            # Display project summaries
            print("\n📈 Project Summaries:")
            for result in analyzer.results:
                print(f"   {result['project_name']}: " +
                      f"{result['summary']['successful_workflows']}/{result['summary']['total_workflows']} workflows successful, " +
                      f"{result['summary']['total_issues']} issues found")

        except Exception as e:
            print(f"❌ Batch analysis failed: {e}")


def create_sample_batch_config():
    """Create a sample batch configuration file."""
    config = {
        "projects": [
            {
                "name": "my-web-app",
                "path": "/path/to/my-web-app",
                "workflows": ["static-analysis", "security-scan"],
                "parameters": {
                    "timeout": 600
                }
            },
            {
                "name": "api-service",
                "path": "/path/to/api-service",
                "workflows": ["dependency-check", "fuzzing"],
                "parameters": {
                    "timeout": 1800
                }
            }
        ],
        "output_directory": "./batch_analysis_results",
        "concurrent_limit": 2,
        "retry_failed": True
    }

    config_file = Path("batch_config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"📄 Sample batch configuration created: {config_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--create-config":
        create_sample_batch_config()
    else:
        print("🔄 Starting batch analysis...")
        print("💡 Use --create-config to generate sample configuration")
        asyncio.run(main())