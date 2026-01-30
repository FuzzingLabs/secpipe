# FuzzForge SDK

A comprehensive Python SDK for the FuzzForge security testing workflow orchestration platform.

## Features

- **Complete API Coverage**: All FuzzForge API endpoints supported
- **File Upload**: Automatic tarball creation and multipart upload for local files
- **Async & Sync**: Both synchronous and asynchronous client methods
- **Real-time Monitoring**: WebSocket and Server-Sent Events for live fuzzing updates
- **Type Safety**: Full Pydantic model validation for all data structures
- **Error Handling**: Comprehensive exception hierarchy with detailed error information
- **Utility Functions**: Helper functions for path validation, SARIF processing, and more

## Installation

Install using uv (recommended):

```bash
uv add fuzzforge-sdk
```

Or with pip:

```bash
pip install fuzzforge-sdk
```

## Quick Start

### Method 1: File Upload (Recommended)

```python
from fuzzforge_sdk import FuzzForgeClient
from pathlib import Path

# Initialize client
client = FuzzForgeClient(base_url="http://localhost:8000")

# List available workflows
workflows = client.list_workflows()

# Submit a workflow with automatic file upload
target_path = Path("/path/to/your/project")
response = client.submit_workflow_with_upload(
    workflow_name="security_assessment",
    target_path=target_path,
    timeout=300
)

# The SDK automatically:
# - Creates a tarball if target_path is a directory
# - Uploads the file to the backend via HTTP
# - Backend stores it in MinIO
# - Returns the workflow run_id

# Wait for completion and get results
final_status = client.wait_for_completion(response.run_id)
findings = client.get_run_findings(response.run_id)

client.close()
```

### Method 2: Path-Based Submission (Legacy)

```python
from fuzzforge_sdk import FuzzForgeClient
from fuzzforge_sdk.utils import create_workflow_submission

# Initialize client
client = FuzzForgeClient(base_url="http://localhost:8000")

# Submit a workflow with path (only works if backend can access the path)
submission = create_workflow_submission(
    target_path="/path/on/backend/filesystem",
    timeout=300
)

response = client.submit_workflow("security_assessment", submission)

client.close()
```

## Examples

The `examples/` directory contains complete working examples:

- **`basic_workflow.py`**: Simple workflow submission and monitoring
- **`fuzzing_monitor.py`**: Real-time fuzzing monitoring with WebSocket/SSE
- **`batch_analysis.py`**: Batch analysis of multiple projects

## File Upload API Reference

### `submit_workflow_with_upload()`

Submit a workflow with automatic file upload from local filesystem.

```python
def submit_workflow_with_upload(
    self,
    workflow_name: str,
    target_path: Union[str, Path],
    parameters: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> RunSubmissionResponse:
    """
    Submit workflow with file upload.

    Args:
        workflow_name: Name of the workflow to execute
        target_path: Path to file or directory to upload
        parameters: Optional workflow parameters
        timeout: Optional execution timeout in seconds
        progress_callback: Optional callback(bytes_sent, total_bytes)

    Returns:
        RunSubmissionResponse with run_id and status

    Raises:
        FileNotFoundError: If target_path doesn't exist
        ValidationError: If parameters are invalid
        FuzzForgeHTTPError: If upload fails
    """
```

**Example with progress tracking:**

```python
from fuzzforge_sdk import FuzzForgeClient
from pathlib import Path

def upload_progress(bytes_sent, total_bytes):
    pct = (bytes_sent / total_bytes) * 100
    print(f"Upload progress: {pct:.1f}% ({bytes_sent}/{total_bytes} bytes)")

client = FuzzForgeClient(base_url="http://localhost:8000")

response = client.submit_workflow_with_upload(
    workflow_name="security_assessment",
    target_path=Path("./my-project"),
    parameters={"check_secrets": True},
    progress_callback=upload_progress
)

print(f"Workflow started: {response.run_id}")
```

### `asubmit_workflow_with_upload()`

Async version of `submit_workflow_with_upload()`.

```python
import asyncio
from fuzzforge_sdk import FuzzForgeClient

async def main():
    client = FuzzForgeClient(base_url="http://localhost:8000")

    response = await client.asubmit_workflow_with_upload(
        workflow_name="security_assessment",
        target_path="/path/to/project",
        parameters={"timeout": 3600}
    )

    print(f"Workflow started: {response.run_id}")
    await client.aclose()

asyncio.run(main())
```

### Internal: `_create_tarball()`

Creates a compressed tarball from a file or directory.

```python
def _create_tarball(
    self,
    source_path: Path,
    progress_callback: Optional[Callable[[int], None]] = None
) -> Path:
    """
    Create compressed tarball (.tar.gz) from source.

    Args:
        source_path: Path to file or directory
        progress_callback: Optional callback(files_added)

    Returns:
        Path to created tarball in temp directory

    Note:
        Caller is responsible for cleaning up the tarball
    """
```

**How it works:**

1. **Directory**: Creates tarball with all files, preserving structure
   ```python
   # For directory: /path/to/project/
   # Creates: /tmp/tmpXXXXXX.tar.gz containing:
   #   project/file1.py
   #   project/subdir/file2.py
   ```

2. **Single file**: Creates tarball with just that file
   ```python
   # For file: /path/to/binary.elf
   # Creates: /tmp/tmpXXXXXX.tar.gz containing:
   #   binary.elf
   ```

### Upload Flow Diagram

```
User Code
   ↓
submit_workflow_with_upload()
   ↓
_create_tarball() ───→ Compress files
   ↓
HTTP POST multipart/form-data
   ↓
Backend API (/workflows/{name}/upload-and-submit)
   ↓
MinIO Storage (S3) ───→ Store with target_id
   ↓
Temporal Workflow
   ↓
Worker downloads from MinIO
   ↓
Workflow execution
```

### Error Handling

The SDK provides detailed error context:

```python
from fuzzforge_sdk import FuzzForgeClient
from fuzzforge_sdk.exceptions import (
    FuzzForgeHTTPError,
    ValidationError,
    ConnectionError
)

client = FuzzForgeClient(base_url="http://localhost:8000")

try:
    response = client.submit_workflow_with_upload(
        workflow_name="security_assessment",
        target_path="./nonexistent",
    )
except FileNotFoundError as e:
    print(f"Target not found: {e}")
except ValidationError as e:
    print(f"Invalid parameters: {e}")
except FuzzForgeHTTPError as e:
    print(f"Upload failed (HTTP {e.status_code}): {e.message}")
    if e.context.response_data:
        print(f"Server response: {e.context.response_data}")
except ConnectionError as e:
    print(f"Cannot connect to backend: {e}")
```

## Development

Install with development dependencies:

```bash
uv sync --extra dev
```