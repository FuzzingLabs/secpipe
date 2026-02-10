# FuzzForge Runner

Direct execution engine for FuzzForge OSS. Provides simplified module and workflow execution without requiring Temporal or external infrastructure.

## Overview

The Runner is designed for local-first operation, executing FuzzForge modules directly in containerized sandboxes (Docker/Podman) without workflow orchestration overhead.

## Features

- Direct module execution in isolated containers
- Sequential workflow orchestration (no Temporal required)
- Local filesystem storage (S3 optional)
- SQLite-based state management (optional)

## Usage

```python
from fuzzforge_runner import Runner
from fuzzforge_runner.settings import Settings

settings = Settings()
runner = Runner(settings)

# Execute a single module
result = await runner.execute_module(
    module_identifier="my-module",
    project_path="/path/to/project",
)

# Execute a workflow (sequential steps)
result = await runner.execute_workflow(
    workflow_definition=workflow,
    project_path="/path/to/project",
)
```

## Configuration

Environment variables:

- `FUZZFORGE_STORAGE_PATH`: Local storage directory (default: `~/.fuzzforge/storage`)
- `FUZZFORGE_ENGINE_TYPE`: Container engine (`docker` or `podman`)
- `FUZZFORGE_ENGINE_SOCKET`: Container socket path
