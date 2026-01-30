# FuzzForge Backend

A stateless API server for security testing workflow orchestration using Temporal. This system dynamically discovers workflows, executes them in isolated worker environments, and returns findings in SARIF format.

## Architecture Overview

### Core Components

1. **Workflow Discovery System**: Automatically discovers workflows at startup
2. **Module System**: Reusable components (scanner, analyzer, reporter) with a common interface
3. **Temporal Integration**: Handles workflow orchestration, execution, and monitoring with vertical workers
4. **File Upload & Storage**: HTTP multipart upload to MinIO for target files
5. **SARIF Output**: Standardized security findings format

### Key Features

- **Stateless**: No persistent data, fully scalable
- **Generic**: No hardcoded workflows, automatic discovery
- **Isolated**: Each workflow runs in specialized vertical workers
- **Extensible**: Easy to add new workflows and modules
- **Secure**: File upload with MinIO storage, automatic cleanup via lifecycle policies
- **Observable**: Comprehensive logging and status tracking

## Quick Start

### Prerequisites

- Docker and Docker Compose

### Installation

From the project root, start all services:

```bash
docker-compose -f docker-compose.temporal.yaml up -d
```

This will start:
- Temporal server (Web UI at http://localhost:8233, gRPC at :7233)
- MinIO (S3 storage at http://localhost:9000, Console at http://localhost:9001)
- PostgreSQL database (for Temporal state)
- Vertical workers (worker-rust, worker-android, worker-web, etc.)
- FuzzForge backend API (port 8000)

**Note**: MinIO console login: `fuzzforge` / `fuzzforge123`

## API Endpoints

### Workflows

- `GET /workflows` - List all discovered workflows
- `GET /workflows/{name}/metadata` - Get workflow metadata and parameters
- `GET /workflows/{name}/parameters` - Get workflow parameter schema
- `GET /workflows/metadata/schema` - Get metadata.yaml schema
- `POST /workflows/{name}/submit` - Submit a workflow for execution (path-based, legacy)
- `POST /workflows/{name}/upload-and-submit` - **Upload local files and submit workflow** (recommended)

### Runs

- `GET /runs/{run_id}/status` - Get run status
- `GET /runs/{run_id}/findings` - Get SARIF findings from completed run
- `GET /runs/{workflow_name}/findings/{run_id}` - Alternative findings endpoint with workflow name

## Workflow Structure

Each workflow must have:

```
toolbox/workflows/{workflow_name}/
   workflow.py       # Temporal workflow definition
   metadata.yaml     # Mandatory metadata (parameters, version, vertical, etc.)
   requirements.txt  # Optional Python dependencies (installed in vertical worker)
```

**Note**: With Temporal architecture, workflows run in pre-built vertical workers (e.g., `worker-rust`, `worker-android`), not individual Docker containers. The workflow code is mounted as a volume and discovered at runtime.

### Example metadata.yaml

```yaml
name: security_assessment
version: "1.0.0"
description: "Comprehensive security analysis workflow"
author: "FuzzForge Team"
category: "comprehensive"
vertical: "rust"  # Routes to worker-rust
tags:
  - "security"
  - "analysis"
  - "comprehensive"

requirements:
  tools:
    - "file_scanner"
    - "security_analyzer"
    - "sarif_reporter"
  resources:
    memory: "512Mi"
    cpu: "500m"
    timeout: 1800

has_docker: true

parameters:
  type: object
  properties:
    target_path:
      type: string
      default: "/workspace"
      description: "Path to analyze"
    scanner_config:
      type: object
      description: "Scanner configuration"
      properties:
        max_file_size:
          type: integer
          description: "Maximum file size to scan (bytes)"

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

### Metadata Field Descriptions

- **name**: Workflow identifier (must match directory name)
- **version**: Semantic version (x.y.z format)
- **description**: Human-readable description of the workflow
- **author**: Workflow author/maintainer
- **category**: Workflow category (comprehensive, specialized, fuzzing, focused)
- **tags**: Array of descriptive tags for categorization
- **requirements.tools**: Required security tools that the workflow uses
- **requirements.resources**: Resource requirements enforced at runtime:
  - `memory`: Memory limit (e.g., "512Mi", "1Gi")
  - `cpu`: CPU limit (e.g., "500m" for 0.5 cores, "1" for 1 core)
  - `timeout`: Maximum execution time in seconds
- **parameters**: JSON Schema object defining workflow parameters
- **output_schema**: Expected output format (typically SARIF)

### Resource Requirements

Resource requirements defined in workflow metadata are automatically enforced. Users can override defaults when submitting workflows:

```bash
curl -X POST "http://localhost:8000/workflows/security_assessment/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/tmp/project",
    "resource_limits": {
      "memory_limit": "1Gi",
      "cpu_limit": "1"
    }
  }'
```

Resource precedence: User limits > Workflow requirements > System defaults

## File Upload and Target Access

### Upload Endpoint

The backend provides an upload endpoint for submitting workflows with local files:

```
POST /workflows/{workflow_name}/upload-and-submit
Content-Type: multipart/form-data

Parameters:
  file: File upload (supports .tar.gz for directories)
  parameters: JSON string of workflow parameters (optional)
  timeout: Execution timeout in seconds (optional)
```

Example using curl:

```bash
# Upload a directory (create tarball first)
tar -czf project.tar.gz /path/to/project
curl -X POST "http://localhost:8000/workflows/security_assessment/upload-and-submit" \
  -F "file=@project.tar.gz" \
  -F "parameters={\"check_secrets\":true}"

# Upload a single file
curl -X POST "http://localhost:8000/workflows/security_assessment/upload-and-submit" \
  -F "file=@binary.elf"
```

### Storage Flow

1. **CLI/API uploads file** via HTTP multipart
2. **Backend receives file** and streams to temporary location (max 10GB)
3. **Backend uploads to MinIO** with generated `target_id`
4. **Workflow is submitted** to Temporal with `target_id`
5. **Worker downloads target** from MinIO to local cache
6. **Workflow processes target** from cache
7. **MinIO lifecycle policy** deletes files after 7 days

### Advantages

- **No host filesystem access required** - workers can run anywhere
- **Automatic cleanup** - lifecycle policies prevent disk exhaustion
- **Caching** - repeated workflows reuse cached targets
- **Multi-host ready** - targets accessible from any worker
- **Secure** - isolated storage, no arbitrary host path access

## Module Development

Modules implement the `BaseModule` interface:

```python
from src.toolbox.modules.base import BaseModule, ModuleMetadata, ModuleResult

class MyModule(BaseModule):
    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="my_module",
            version="1.0.0",
            description="Module description",
            category="scanner",
            ...
        )

    async def execute(self, config: Dict, workspace: Path) -> ModuleResult:
        # Module logic here
        findings = [...]
        return self.create_result(findings=findings)

    def validate_config(self, config: Dict) -> bool:
        # Validate configuration
        return True
```

## Submitting a Workflow

### With File Upload (Recommended)

```bash
# Automatic tarball and upload
tar -czf project.tar.gz /home/user/project
curl -X POST "http://localhost:8000/workflows/security_assessment/upload-and-submit" \
  -F "file=@project.tar.gz" \
  -F "parameters={\"scanner_config\":{\"patterns\":[\"*.py\"]},\"analyzer_config\":{\"check_secrets\":true}}"
```

### Legacy Path-Based Submission

```bash
# Only works if backend and target are on same machine
curl -X POST "http://localhost:8000/workflows/security_assessment/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/home/user/project",
    "parameters": {
      "scanner_config": {"patterns": ["*.py"]},
      "analyzer_config": {"check_secrets": true}
    }
  }'
```

## Getting Findings

```bash
curl "http://localhost:8000/runs/{run_id}/findings"
```

Returns SARIF-formatted findings:

```json
{
  "workflow": "security_assessment",
  "run_id": "abc-123",
  "sarif": {
    "version": "2.1.0",
    "runs": [{
      "tool": {...},
      "results": [...]
    }]
  }
}
```

## Security Considerations

1. **File Upload Security**: Files uploaded to MinIO with isolated storage
2. **Read-Only Default**: Target files accessed as read-only unless explicitly set
3. **Worker Isolation**: Each workflow runs in isolated vertical workers
4. **Resource Limits**: Can set CPU/memory limits per worker
5. **Automatic Cleanup**: MinIO lifecycle policies delete old files after 7 days

## Development

### Adding a New Workflow

1. Create directory: `toolbox/workflows/my_workflow/`
2. Add `workflow.py` with a Temporal workflow (using `@workflow.defn`)
3. Add mandatory `metadata.yaml` with `vertical` field
4. Restart the appropriate worker: `docker-compose -f docker-compose.temporal.yaml restart worker-rust`
5. Worker will automatically discover and register the new workflow

### Adding a New Module

1. Create module in `toolbox/modules/{category}/`
2. Implement `BaseModule` interface
3. Use in workflows via import

### Adding a New Vertical Worker

1. Create worker directory: `workers/{vertical}/`
2. Create `Dockerfile` with required tools
3. Add worker to `docker-compose.temporal.yaml`
4. Worker will automatically discover workflows with matching `vertical` in metadata