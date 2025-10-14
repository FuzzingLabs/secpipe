# How to Create a Custom Workflow in FuzzForge

This guide will walk you through the process of creating a custom security analysis workflow in FuzzForge. Workflows orchestrate modules, define the analysis pipeline, and enable you to automate complex security checks for your codebase or application.

---

## Prerequisites

Before you start, make sure you have:

- A working FuzzForge development environment (see [Contributing](/reference/contributing.md))
- Familiarity with Python (async/await), Docker, and Temporal
- At least one custom or built-in module to use in your workflow

---

## Step 1: Understand Workflow Architecture

A FuzzForge workflow is a Temporal workflow that:

- Runs inside a long-lived vertical worker container (pre-built with toolchains)
- Orchestrates one or more analysis modules (scanner, analyzer, reporter, etc.)
- Downloads targets from MinIO (S3-compatible storage) automatically
- Produces standardized SARIF output
- Supports configurable parameters and resource limits

**Directory structure:**

```
backend/toolbox/workflows/{workflow_name}/
├── workflow.py          # Main workflow definition (Temporal workflow)
├── activities.py        # Workflow activities (optional)
├── metadata.yaml        # Workflow metadata and configuration (must include vertical field)
└── requirements.txt     # Additional Python dependencies (optional)
```

---

## Step 2: Define Workflow Metadata

Create a `metadata.yaml` file in your workflow directory. This file describes your workflow, its parameters, and resource requirements.

Example:

```yaml
name: dependency_analysis
version: "1.0.0"
description: "Analyzes project dependencies for security vulnerabilities"
author: "FuzzingLabs Security Team"
category: "comprehensive"
vertical: "web"  # REQUIRED: Which vertical worker to use (rust, android, web, etc.)
tags:
  - "dependency-scanning"
  - "vulnerability-analysis"
requirements:
  tools:
    - "dependency_scanner"
    - "vulnerability_analyzer"
    - "sarif_reporter"
  resources:
    memory: "512Mi"
    cpu: "1000m"
    timeout: 1800
parameters:
  type: object
  properties:
    scan_dev_dependencies:
      type: boolean
      description: "Include development dependencies"
    vulnerability_threshold:
      type: string
      enum: ["low", "medium", "high", "critical"]
      description: "Minimum vulnerability severity to report"
output_schema:
  type: object
  properties:
    sarif:
      type: object
      description: "SARIF-formatted security findings"
    summary:
      type: object
      description: "Scan execution summary"
```

**Important:** The `vertical` field determines which worker runs your workflow. Ensure the worker has the required tools installed.

### Workspace Isolation

Add the `workspace_isolation` field to control how workflow runs share or isolate workspaces:

```yaml
# Workspace isolation mode (system-level configuration)
# - "isolated" (default): Each workflow run gets its own isolated workspace
# - "shared": All runs share the same workspace (for read-only workflows)
# - "copy-on-write": Download once, copy for each run
workspace_isolation: "isolated"
```

**Choosing the right mode:**

- **`isolated`** (default) - For fuzzing workflows that modify files (corpus, crashes)
  - Example: `atheris_fuzzing`, `cargo_fuzzing`
  - Safe for concurrent execution

- **`shared`** - For read-only analysis workflows
  - Example: `security_assessment`, `secret_detection`
  - Efficient (downloads once, reuses cache)

- **`copy-on-write`** - For large targets that need isolation
  - Downloads once, copies per run
  - Balances performance and isolation

See the [Workspace Isolation](/concept/workspace-isolation) guide for details.

---

## Step 3: Add Live Statistics to Your Workflow 🚦

Want real-time progress and stats for your workflow? FuzzForge supports live statistics reporting using Temporal workflow logging. This lets users (and the platform) monitor workflow progress, see live updates, and stream stats via API or WebSocket.

### 1. Import Required Dependencies

```python
from temporalio import workflow, activity
import logging

logger = logging.getLogger(__name__)
```

### 2. Create a Statistics Callback in Activity

Add a callback that logs structured stats updates in your activity:

```python
@activity.defn
async def my_workflow_activity(target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    # Get activity info for run tracking
    info = activity.info()
    run_id = info.workflow_id

    logger.info(f"Running activity for workflow: {run_id}")

    # Define callback function for live statistics
    async def stats_callback(stats_data: Dict[str, Any]):
        """Callback to handle live statistics"""
        try:
            # Log structured statistics data for the backend to parse
            logger.info("LIVE_STATS", extra={
                "stats_type": "live_stats",           # Type of statistics
                "workflow_type": "my_workflow",       # Your workflow name
                "run_id": run_id,

                # Add your custom statistics fields here:
                "progress": stats_data.get("progress", 0),
                "items_processed": stats_data.get("items_processed", 0),
                "errors": stats_data.get("errors", 0),
                "elapsed_time": stats_data.get("elapsed_time", 0),
                "timestamp": stats_data.get("timestamp")
            })
        except Exception as e:
            logger.warning(f"Error in stats callback: {e}")

    # Pass callback to your module/processor
    processor = MyWorkflowModule()
    result = await processor.execute(config, target_path, stats_callback=stats_callback)
    return result.dict()
```

### 3. Update Your Module to Use the Callback

```python
class MyWorkflowModule:
    async def execute(self, config: Dict[str, Any], workspace: Path, stats_callback=None):
        # Your processing logic here

        # Periodically send statistics updates
        if stats_callback:
            await stats_callback({
                "run_id": run_id,
                "progress": current_progress,
                "items_processed": processed_count,
                "errors": error_count,
                "elapsed_time": elapsed_seconds,
                "timestamp": datetime.utcnow().isoformat()
            })
```

### 4. Supported Statistics Types

The monitor recognizes these `stats_type` values:

- `"fuzzing_live_update"` - For fuzzing workflows (uses FuzzingStats model)
- `"scan_progress"` - For security scanning workflows
- `"analysis_update"` - For code analysis workflows
- `"live_stats"` - Generic live statistics for any workflow

#### Example: Fuzzing Workflow Stats

```python
"stats_type": "fuzzing_live_update",
"executions": 12345,
"executions_per_sec": 1500.0,
"crashes": 2,
"unique_crashes": 2,
"corpus_size": 45,
"coverage": 78.5,
"elapsed_time": 120
```

#### Example: Scanning Workflow Stats

```python
"stats_type": "scan_progress",
"files_scanned": 150,
"vulnerabilities_found": 8,
"scan_percentage": 65.2,
"current_file": "/path/to/file.js",
"elapsed_time": 45
```

#### Example: Analysis Workflow Stats

```python
"stats_type": "analysis_update",
"functions_analyzed": 89,
"issues_found": 12,
"complexity_score": 7.8,
"current_module": "authentication",
"elapsed_time": 30
```

### 5. API Integration

Live statistics automatically appear in:

- **REST API**: `GET /fuzzing/{run_id}/stats` (for fuzzing workflows)
- **WebSocket**: Real-time updates via WebSocket connections
- **Server-Sent Events**: Live streaming at `/fuzzing/{run_id}/stream`

### 6. Best Practices

1. **Update Frequency**: Send statistics every 5-10 seconds for optimal performance.
2. **Error Handling**: Always wrap stats callbacks in try-catch blocks.
3. **Meaningful Data**: Include workflow-specific metrics that users care about.
4. **Consistent Naming**: Use consistent field names across similar workflow types.
5. **Backwards Compatibility**: Keep existing stats types when updating workflows.

#### Example: Adding Stats to a Security Scanner

```python
@activity.defn
async def security_scan_activity(target_path: str, config: Dict[str, Any]):
    info = activity.info()
    run_id = info.workflow_id

    async def stats_callback(stats_data):
        logger.info("LIVE_STATS", extra={
            "stats_type": "scan_progress",
            "workflow_type": "security_scan",
            "run_id": run_id,
            "files_scanned": stats_data.get("files_scanned", 0),
            "vulnerabilities_found": stats_data.get("vulnerabilities_found", 0),
            "scan_percentage": stats_data.get("scan_percentage", 0.0),
            "current_file": stats_data.get("current_file", ""),
            "elapsed_time": stats_data.get("elapsed_time", 0)
        })

    scanner = SecurityScannerModule()
    return await scanner.execute(config, target_path, stats_callback=stats_callback)
```

With these steps, your workflow will provide rich, real-time feedback to users and the FuzzForge platform—making automation more transparent and interactive!

---

## Step 4: Implement the Workflow Logic

Create a `workflow.py` file. This is where you define your Temporal workflow and activities.

Example (simplified):

```python
from pathlib import Path
from typing import Dict, Any
from temporalio import workflow, activity
from datetime import timedelta
from src.toolbox.modules.dependency_scanner import DependencyScanner
from src.toolbox.modules.vulnerability_analyzer import VulnerabilityAnalyzer
from src.toolbox.modules.reporter import SARIFReporter

@activity.defn
async def scan_dependencies(target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    scanner = DependencyScanner()
    return (await scanner.execute(config, target_path)).dict()

@activity.defn
async def analyze_vulnerabilities(dependencies: Dict[str, Any], target_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    analyzer = VulnerabilityAnalyzer()
    analyzer_config = {**config, 'dependencies': dependencies.get('findings', [])}
    return (await analyzer.execute(analyzer_config, target_path)).dict()

@activity.defn
async def generate_report(dep_results: Dict[str, Any], vuln_results: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    reporter = SARIFReporter()
    all_findings = dep_results.get("findings", []) + vuln_results.get("findings", [])
    reporter_config = {**config, "findings": all_findings}
    return (await reporter.execute(reporter_config, None)).dict().get("sarif", {})

@workflow.defn
class DependencyAnalysisWorkflow:
    @workflow.run
    async def run(
        self,
        target_id: str,  # Target file ID from MinIO (downloaded by worker automatically)
        scan_dev_dependencies: bool = True,
        vulnerability_threshold: str = "medium"
    ) -> Dict[str, Any]:
        workflow.logger.info(f"Starting dependency analysis for target: {target_id}")

        # Get run ID for workspace isolation
        run_id = workflow.info().run_id

        # Worker downloads target from MinIO with isolation
        target_path = await workflow.execute_activity(
            "get_target",
            args=[target_id, run_id, "shared"],  # target_id, run_id, workspace_isolation
            start_to_close_timeout=timedelta(minutes=5)
        )

        scanner_config = {"scan_dev_dependencies": scan_dev_dependencies}
        analyzer_config = {"vulnerability_threshold": vulnerability_threshold}

        # Execute activities with retries and timeouts
        dep_results = await workflow.execute_activity(
            scan_dependencies,
            args=[target_path, scanner_config],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=workflow.RetryPolicy(maximum_attempts=3)
        )

        vuln_results = await workflow.execute_activity(
            analyze_vulnerabilities,
            args=[dep_results, target_path, analyzer_config],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=workflow.RetryPolicy(maximum_attempts=3)
        )

        sarif_report = await workflow.execute_activity(
            generate_report,
            args=[dep_results, vuln_results, {}],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=workflow.RetryPolicy(maximum_attempts=3)
        )

        # Cleanup cache (respects isolation mode)
        await workflow.execute_activity(
            "cleanup_cache",
            args=[target_path, "shared"],  # target_path, workspace_isolation
            start_to_close_timeout=timedelta(minutes=1)
        )

        workflow.logger.info("Dependency analysis completed")
        return sarif_report
```

**Key Temporal Workflow Concepts:**
- Use `@workflow.defn` class decorator to define workflows
- Use `@activity.defn` decorator for activity functions
- Call `get_target` activity to download targets from MinIO with workspace isolation
- Use `workflow.execute_activity()` with explicit timeouts and retry policies
- Use `workflow.logger` for logging (appears in Temporal UI and backend logs)
- Call `cleanup_cache` activity at end to clean up workspace

---

## Step 5: No Dockerfile Needed! 🎉

**Good news:** You don't need to create a Dockerfile for your workflow. Workflows run inside pre-built **vertical worker containers** that already have toolchains installed.

**How it works:**
1. Your workflow code lives in `backend/toolbox/workflows/{workflow_name}/`
2. This directory is **mounted as a volume** in the worker container at `/app/toolbox/workflows/`
3. Worker discovers and registers your workflow automatically on startup
4. When submitted, the workflow runs inside the long-lived worker container

**Benefits:**
- Zero container build time per workflow
- Instant code changes (just restart worker)
- All toolchains pre-installed (AFL++, cargo-fuzz, apktool, etc.)
- Consistent environment across all workflows of the same vertical

---

## Step 6: Test Your Workflow

### Using the CLI

```bash
# Start FuzzForge with Temporal
docker-compose -f docker-compose.temporal.yaml up -d

# Wait for services to initialize
sleep 10

# Submit workflow with file upload
cd test_projects/vulnerable_app/
fuzzforge workflow run dependency_analysis .

# CLI automatically:
# - Creates tarball of current directory
# - Uploads to MinIO via backend
# - Submits workflow with target_id
# - Worker downloads from MinIO and executes
```

### Using Python SDK

```python
from fuzzforge_sdk import FuzzForgeClient
from pathlib import Path

client = FuzzForgeClient(base_url="http://localhost:8000")

# Submit with automatic upload
response = client.submit_workflow_with_upload(
    workflow_name="dependency_analysis",
    target_path=Path("/path/to/project"),
    parameters={
        "scan_dev_dependencies": True,
        "vulnerability_threshold": "medium"
    }
)

print(f"Workflow started: {response.run_id}")

# Wait for completion
final_status = client.wait_for_completion(response.run_id)

# Get findings
findings = client.get_run_findings(response.run_id)
print(findings.sarif)

client.close()
```

### Check Temporal UI

Open http://localhost:8233 to see:
- Workflow execution timeline
- Activity results
- Logs and errors
- Retry history

---

## Best Practices

- **Parameterize everything:** Use metadata.yaml to define all configurable options.
- **Validate inputs:** Check that paths, configs, and parameters are valid before running analysis.
- **Handle errors gracefully:** Catch exceptions in tasks and return partial results if possible.
- **Document your workflow:** Add docstrings and comments to explain each step.
- **Test with real and edge-case projects:** Ensure your workflow is robust and reliable.
