# FuzzForge Temporal Architecture - Quick Start Guide

This guide walks you through starting and testing the new Temporal-based architecture.

## Prerequisites

- Docker and Docker Compose installed
- At least 2GB free RAM (core services only, workers start on-demand)
- Ports available: 7233, 8233, 9000, 9001, 8000

## Step 1: Start Core Services

```bash
# From project root
cd /path/to/fuzzforge_ai

# Start core services (Temporal, MinIO, Backend)
docker-compose up -d

# Workers are pre-built but don't auto-start (saves ~6-7GB RAM)
# They'll start automatically when workflows need them

# Check status
docker-compose ps
```

**Expected output:**
```
NAME                          STATUS    PORTS
fuzzforge-minio               healthy   0.0.0.0:9000-9001->9000-9001/tcp
fuzzforge-temporal            healthy   0.0.0.0:7233->7233/tcp
fuzzforge-temporal-postgresql healthy   5432/tcp
fuzzforge-backend             healthy   0.0.0.0:8000->8000/tcp
fuzzforge-minio-setup         exited (0)
# Workers NOT running (will start on-demand)
```

**First startup takes ~30-60 seconds** for health checks to pass.

## Step 2: Verify Worker Discovery

Check worker logs to ensure workflows are discovered:

```bash
docker logs fuzzforge-worker-rust
```

**Expected output:**
```
============================================================
FuzzForge Vertical Worker: rust
============================================================
Temporal Address: temporal:7233
Task Queue: rust-queue
Max Concurrent Activities: 5
============================================================
Discovering workflows for vertical: rust
Importing workflow module: toolbox.workflows.rust_test.workflow
✓ Discovered workflow: RustTestWorkflow from rust_test (vertical: rust)
Discovered 1 workflows for vertical 'rust'
Connecting to Temporal at temporal:7233...
✓ Connected to Temporal successfully
Creating worker on task queue: rust-queue
✓ Worker created successfully
============================================================
🚀 Worker started for vertical 'rust'
📦 Registered 1 workflows
⚙️  Registered 3 activities
📨 Listening on task queue: rust-queue
============================================================
Worker is ready to process tasks...
```

## Step 2.5: Worker Lifecycle Management (New in v0.7.0)

Workers start on-demand when workflows need them:

```bash
# Check worker status (should show Exited or not running)
docker ps -a --filter "name=fuzzforge-worker"

# Run a workflow - worker starts automatically
ff workflow run ossfuzz_campaign . project_name=zlib

# Worker is now running
docker ps --filter "name=fuzzforge-worker-ossfuzz"
```

**Configuration** (`.fuzzforge/config.yaml`):
```yaml
workers:
  auto_start_workers: true    # Default: auto-start
  auto_stop_workers: false    # Default: keep running
  worker_startup_timeout: 60  # Startup timeout in seconds
```

**CLI Control**:
```bash
# Disable auto-start
ff workflow run ossfuzz_campaign . --no-auto-start

# Enable auto-stop after completion
ff workflow run ossfuzz_campaign . --wait --auto-stop
```

## Step 3: Access Web UIs

### Temporal Web UI
- URL: http://localhost:8233
- View workflows, executions, and task queues

### MinIO Console
- URL: http://localhost:9001
- Login: `fuzzforge` / `fuzzforge123`
- View uploaded targets and results

## Step 4: Test Workflow Execution

### Option A: Using Temporal CLI (tctl)

```bash
# Install tctl (if not already installed)
brew install temporal  # macOS
# or download from https://github.com/temporalio/tctl/releases

# Execute test workflow
tctl workflow run \
  --address localhost:7233 \
  --taskqueue rust-queue \
  --workflow_type RustTestWorkflow \
  --input '{"target_id": "test-123", "test_message": "Hello Temporal!"}'
```

### Option B: Using Python Client

Create `test_workflow.py`:

```python
import asyncio
from temporalio.client import Client

async def main():
    # Connect to Temporal
    client = await Client.connect("localhost:7233")

    # Start workflow
    result = await client.execute_workflow(
        "RustTestWorkflow",
        {"target_id": "test-123", "test_message": "Hello Temporal!"},
        id="test-workflow-1",
        task_queue="rust-queue"
    )

    print("Workflow result:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

```bash
python test_workflow.py
```

### Option C: Upload Target and Run (Full Flow)

```python
# upload_and_run.py
import asyncio
import boto3
from pathlib import Path
from temporalio.client import Client

async def main():
    # 1. Upload target to MinIO
    s3 = boto3.client(
        's3',
        endpoint_url='http://localhost:9000',
        aws_access_key_id='fuzzforge',
        aws_secret_access_key='fuzzforge123',
        region_name='us-east-1'
    )

    # Create a test file
    test_file = Path('/tmp/test_target.txt')
    test_file.write_text('This is a test target file')

    # Upload to MinIO
    target_id = 'my-test-target-001'
    s3.upload_file(
        str(test_file),
        'targets',
        f'{target_id}/target'
    )
    print(f"✓ Uploaded target: {target_id}")

    # 2. Run workflow
    client = await Client.connect("localhost:7233")

    result = await client.execute_workflow(
        "RustTestWorkflow",
        {"target_id": target_id, "test_message": "Full flow test!"},
        id=f"workflow-{target_id}",
        task_queue="rust-queue"
    )

    print("✓ Workflow completed!")
    print("Results:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

```bash
# Install dependencies
pip install temporalio boto3

# Run test
python upload_and_run.py
```

## Step 5: Monitor Execution

### View in Temporal UI

1. Open http://localhost:8233
2. Click on "Workflows"
3. Find your workflow by ID
4. Click to see:
   - Execution history
   - Activity results
   - Error stack traces (if any)

### View Logs

```bash
# Worker logs (shows activity execution)
docker logs -f fuzzforge-worker-rust

# Temporal server logs
docker logs -f fuzzforge-temporal
```

### Check MinIO Storage

1. Open http://localhost:9001
2. Login: `fuzzforge` / `fuzzforge123`
3. Browse buckets:
   - `targets/` - Uploaded target files
   - `results/` - Workflow results (if uploaded)
   - `cache/` - Worker cache (temporary)

## Troubleshooting

### Services Not Starting

```bash
# Check logs for all services
docker-compose -f docker-compose.temporal.yaml logs

# Check specific service
docker-compose -f docker-compose.temporal.yaml logs temporal
docker-compose -f docker-compose.temporal.yaml logs minio
docker-compose -f docker-compose.temporal.yaml logs worker-rust
```

### Worker Not Discovering Workflows

**Issue**: Worker logs show "No workflows found for vertical: rust"

**Solution**:
1. Check toolbox mount: `docker exec fuzzforge-worker-rust ls /app/toolbox/workflows`
2. Verify metadata.yaml exists and has `vertical: rust`
3. Check workflow.py has `@workflow.defn` decorator

### Cannot Connect to Temporal

**Issue**: `Failed to connect to Temporal`

**Solution**:
```bash
# Wait for Temporal to be healthy
docker-compose -f docker-compose.temporal.yaml ps

# Check Temporal health manually
curl http://localhost:8233

# Restart Temporal if needed
docker-compose -f docker-compose.temporal.yaml restart temporal
```

### MinIO Connection Failed

**Issue**: `Failed to download target`

**Solution**:
```bash
# Check MinIO is running
docker ps | grep minio

# Check buckets exist
docker exec fuzzforge-minio mc ls fuzzforge/

# Verify target was uploaded
docker exec fuzzforge-minio mc ls fuzzforge/targets/
```

### Workflow Hangs

**Issue**: Workflow starts but never completes

**Check**:
1. Worker logs for errors: `docker logs fuzzforge-worker-rust`
2. Activity timeouts in workflow code
3. Target file actually exists in MinIO

## Scaling

### Add More Workers

```bash
# Scale rust workers horizontally
docker-compose -f docker-compose.temporal.yaml up -d --scale worker-rust=3

# Verify all workers are running
docker ps | grep worker-rust
```

### Increase Concurrent Activities

Edit `docker-compose.temporal.yaml`:

```yaml
worker-rust:
  environment:
    MAX_CONCURRENT_ACTIVITIES: 10  # Increase from 5
```

```bash
# Apply changes
docker-compose -f docker-compose.temporal.yaml up -d worker-rust
```

## Cleanup

```bash
# Stop all services
docker-compose -f docker-compose.temporal.yaml down

# Remove volumes (WARNING: deletes all data)
docker-compose -f docker-compose.temporal.yaml down -v

# Remove everything including images
docker-compose -f docker-compose.temporal.yaml down -v --rmi all
```

## Next Steps

1. **Add More Workflows**: Create workflows in `backend/toolbox/workflows/`
2. **Add More Verticals**: Create new worker types (android, web, etc.) - see `workers/README.md`
3. **Integrate with Backend**: Update FastAPI backend to use Temporal client
4. **Update CLI**: Modify `ff` CLI to work with Temporal workflows

## Useful Commands

```bash
# View all logs
docker-compose -f docker-compose.temporal.yaml logs -f

# View specific service logs
docker-compose -f docker-compose.temporal.yaml logs -f worker-rust

# Restart a service
docker-compose -f docker-compose.temporal.yaml restart worker-rust

# Check service status
docker-compose -f docker-compose.temporal.yaml ps

# Execute command in worker
docker exec -it fuzzforge-worker-rust bash

# View worker Python environment
docker exec fuzzforge-worker-rust pip list

# Check workflow discovery manually
docker exec fuzzforge-worker-rust python -c "
from pathlib import Path
import yaml
for w in Path('/app/toolbox/workflows').iterdir():
    if w.is_dir():
        meta = w / 'metadata.yaml'
        if meta.exists():
            print(f'{w.name}: {yaml.safe_load(meta.read_text()).get(\"vertical\")}')"
```

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Temporal  │────▶│  Task Queue  │────▶│ Worker-Rust  │
│   Server    │     │  rust-queue  │     │  (Long-lived)│
└─────────────┘     └──────────────┘     └──────┬───────┘
       │                                         │
       │                                         │
       ▼                                         ▼
┌─────────────┐                          ┌──────────────┐
│  Postgres   │                          │    MinIO     │
│  (State)    │                          │  (Storage)   │
└─────────────┘                          └──────────────┘
                                                │
                                         ┌──────┴──────┐
                                         │             │
                                    ┌────▼────┐  ┌─────▼────┐
                                    │ Targets │  │ Results  │
                                    └─────────┘  └──────────┘
```

## Support

- **Documentation**: See `ARCHITECTURE.md` for detailed design
- **Worker Guide**: See `workers/README.md` for adding verticals
- **Issues**: Open GitHub issue with logs and steps to reproduce
