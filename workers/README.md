# FuzzForge Vertical Workers

This directory contains vertical-specific worker implementations for the Temporal architecture.

## Architecture

Each vertical worker is a long-lived container pre-built with domain-specific security toolchains:

```
workers/
├── rust/           # Rust/Native security (AFL++, cargo-fuzz, gdb, valgrind)
├── android/        # Android security (apktool, Frida, jadx, MobSF)
├── web/            # Web security (OWASP ZAP, semgrep, eslint)
├── ios/            # iOS security (class-dump, Clutch, Frida)
├── blockchain/     # Smart contract security (mythril, slither, echidna)
└── go/             # Go security (go-fuzz, staticcheck, gosec)
```

## How It Works

1. **Worker Startup**: Worker discovers workflows from `/app/toolbox/workflows`
2. **Filtering**: Only loads workflows where `metadata.yaml` has `vertical: <name>`
3. **Dynamic Import**: Dynamically imports workflow Python modules
4. **Registration**: Registers discovered workflows with Temporal
5. **Processing**: Polls Temporal task queue for work

## Adding a New Vertical

### Step 1: Create Worker Directory

```bash
mkdir -p workers/my_vertical
cd workers/my_vertical
```

### Step 2: Create Dockerfile

```dockerfile
# workers/my_vertical/Dockerfile
FROM python:3.11-slim

# Install your vertical-specific tools
RUN apt-get update && apt-get install -y \
    tool1 \
    tool2 \
    tool3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy worker files
COPY worker.py /app/worker.py
COPY activities.py /app/activities.py

WORKDIR /app
ENV PYTHONPATH="/app:/app/toolbox:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

CMD ["python", "worker.py"]
```

### Step 3: Copy Worker Files

```bash
# Copy from rust worker as template
cp workers/rust/worker.py workers/my_vertical/
cp workers/rust/activities.py workers/my_vertical/
cp workers/rust/requirements.txt workers/my_vertical/
```

**Note**: The worker.py and activities.py are generic and work for all verticals. You only need to customize the Dockerfile with your tools.

### Step 4: Add to docker-compose.yml

Add profiles to prevent auto-start:

```yaml
worker-my-vertical:
  build:
    context: ./workers/my_vertical
    dockerfile: Dockerfile
  container_name: fuzzforge-worker-my-vertical
  profiles:          # ← Prevents auto-start (saves RAM)
    - workers
    - my_vertical
  depends_on:
    temporal:
      condition: service_healthy
    minio:
      condition: service_healthy
  environment:
    TEMPORAL_ADDRESS: temporal:7233
    WORKER_VERTICAL: my_vertical  # ← Important: matches metadata.yaml
    WORKER_TASK_QUEUE: my-vertical-queue
    MAX_CONCURRENT_ACTIVITIES: 5
    # MinIO configuration (same for all workers)
    STORAGE_BACKEND: s3
    S3_ENDPOINT: http://minio:9000
    S3_ACCESS_KEY: fuzzforge
    S3_SECRET_KEY: fuzzforge123
    S3_BUCKET: targets
    CACHE_DIR: /cache
  volumes:
    - ./backend/toolbox:/app/toolbox:ro
    - worker_my_vertical_cache:/cache
  networks:
    - fuzzforge-network
  restart: "no"      # ← Don't auto-restart
```

**Why profiles?** Workers are pre-built but don't auto-start, saving ~1-2GB RAM per worker when idle.

### Step 5: Add Volume

```yaml
volumes:
  worker_my_vertical_cache:
    name: fuzzforge_worker_my_vertical_cache
```

### Step 6: Create Workflows for Your Vertical

```bash
mkdir -p backend/toolbox/workflows/my_workflow
```

**metadata.yaml:**
```yaml
name: my_workflow
version: 1.0.0
vertical: my_vertical  # ← Must match WORKER_VERTICAL
```

**workflow.py:**
```python
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, target_id: str) -> dict:
        # Download target
        target_path = await workflow.execute_activity(
            "get_target",
            target_id,
            start_to_close_timeout=timedelta(minutes=5)
        )

        # Your analysis logic here
        results = {"status": "success"}

        # Cleanup
        await workflow.execute_activity(
            "cleanup_cache",
            target_path,
            start_to_close_timeout=timedelta(minutes=1)
        )

        return results
```

### Step 7: Test

```bash
# Start services
docker-compose -f docker-compose.temporal.yaml up -d

# Check worker logs
docker logs -f fuzzforge-worker-my-vertical

# You should see:
# "Discovered workflow: MyWorkflow from my_workflow (vertical: my_vertical)"
```

## Worker Components

### worker.py

Generic worker entrypoint. Handles:
- Workflow discovery from mounted `/app/toolbox`
- Dynamic import of workflow modules
- Connection to Temporal
- Task queue polling

**No customization needed** - works for all verticals.

### activities.py

Common activities available to all workflows:

- `get_target(target_id: str) -> str`: Download target from MinIO
- `cleanup_cache(target_path: str) -> None`: Remove cached target
- `upload_results(workflow_id, results, format) -> str`: Upload results to MinIO

**Can be extended** with vertical-specific activities:

```python
# workers/my_vertical/activities.py

from temporalio import activity

@activity.defn(name="my_custom_activity")
async def my_custom_activity(input_data: str) -> str:
    # Your vertical-specific logic
    return "result"

# Add to worker.py activities list:
# activities=[..., my_custom_activity]
```

### Dockerfile

**Only component that needs customization** for each vertical. Install your tools here.

## Configuration

### Environment Variables

All workers support these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `WORKER_VERTICAL` | `rust` | Vertical name (must match metadata.yaml) |
| `WORKER_TASK_QUEUE` | `{vertical}-queue` | Task queue name |
| `MAX_CONCURRENT_ACTIVITIES` | `5` | Max concurrent activities per worker |
| `S3_ENDPOINT` | `http://minio:9000` | MinIO/S3 endpoint |
| `S3_ACCESS_KEY` | `fuzzforge` | S3 access key |
| `S3_SECRET_KEY` | `fuzzforge123` | S3 secret key |
| `S3_BUCKET` | `targets` | Bucket for uploaded targets |
| `CACHE_DIR` | `/cache` | Local cache directory |
| `CACHE_MAX_SIZE` | `10GB` | Max cache size (not enforced yet) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Scaling

### Vertical Scaling (More Work Per Worker)

Increase concurrent activities:

```yaml
environment:
  MAX_CONCURRENT_ACTIVITIES: 10  # Handle 10 tasks at once
```

### Horizontal Scaling (More Workers)

```bash
# Scale to 3 workers for rust vertical
docker-compose -f docker-compose.temporal.yaml up -d --scale worker-rust=3

# Each worker polls the same task queue
# Temporal automatically load balances
```

## Troubleshooting

### Worker Not Discovering Workflows

Check:
1. Volume mount is correct: `./backend/toolbox:/app/toolbox:ro`
2. Workflow has `metadata.yaml` with correct `vertical:` field
3. Workflow has `workflow.py` with `@workflow.defn` decorated class
4. Worker logs show discovery attempt

### Cannot Connect to Temporal

Check:
1. Temporal container is healthy: `docker ps`
2. Network connectivity: `docker exec worker-rust ping temporal`
3. `TEMPORAL_ADDRESS` environment variable is correct

### Cannot Download from MinIO

Check:
1. MinIO is healthy: `docker ps`
2. Buckets exist: `docker exec fuzzforge-minio mc ls fuzzforge/targets`
3. S3 credentials are correct
4. Target was uploaded: Check MinIO console at http://localhost:9001

### Activity Timeouts

Increase timeout in workflow:

```python
await workflow.execute_activity(
    "my_activity",
    args,
    start_to_close_timeout=timedelta(hours=2)  # Increase from default
)
```

## Best Practices

1. **Keep Dockerfiles lean**: Only install necessary tools
2. **Use multi-stage builds**: Reduce final image size
3. **Pin tool versions**: Ensure reproducibility
4. **Log liberally**: Helps debugging workflow issues
5. **Handle errors gracefully**: Don't fail workflow for non-critical issues
6. **Test locally first**: Use docker-compose before deploying

## On-Demand Worker Management

Workers use Docker Compose profiles and CLI-managed lifecycle for resource optimization.

### How It Works

1. **Build Time**: `docker-compose build` creates all worker images
2. **Startup**: Workers DON'T auto-start with `docker-compose up -d`
3. **On Demand**: CLI starts workers automatically when workflows need them
4. **Shutdown**: Optional auto-stop after workflow completion

### Manual Control

```bash
# Start specific worker
docker start fuzzforge-worker-ossfuzz

# Stop specific worker
docker stop fuzzforge-worker-ossfuzz

# Check worker status
docker ps --filter "name=fuzzforge-worker"
```

### CLI Auto-Management

```bash
# Auto-start enabled by default
ff workflow run ossfuzz_campaign . project_name=zlib

# Disable auto-start
ff workflow run ossfuzz_campaign . project_name=zlib --no-auto-start

# Auto-stop after completion
ff workflow run ossfuzz_campaign . project_name=zlib --wait --auto-stop
```

### Resource Savings

- **Before**: All workers running = ~8GB RAM
- **After**: Only core services running = ~1.2GB RAM
- **Savings**: ~6-7GB RAM when idle

## Examples

See existing verticals for examples:
- `workers/rust/` - Complete working example
- `backend/toolbox/workflows/rust_test/` - Simple test workflow
