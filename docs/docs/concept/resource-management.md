# Resource Management in FuzzForge

FuzzForge uses a multi-layered approach to manage CPU, memory, and concurrency for workflow execution. This ensures stable operation, prevents resource exhaustion, and allows predictable performance.

---

## Overview

Resource limiting in FuzzForge operates at three levels:

1. **Docker Container Limits** (Primary Enforcement) - Hard limits enforced by Docker
2. **Worker Concurrency Limits** - Controls parallel workflow execution
3. **Workflow Metadata** (Advisory) - Documents resource requirements

---

## Worker Lifecycle Management (On-Demand Startup)

**New in v0.7.0**: Workers now support on-demand startup/shutdown for optimal resource usage.

### Architecture

Workers are **pre-built** but **not auto-started**:

```
┌─────────────┐
│ docker-     │  Pre-built worker images
│ compose     │  with profiles: ["workers", "ossfuzz"]
│ build       │  restart: "no"
└─────────────┘
       ↓
┌─────────────┐
│ Workers     │  Status: Exited (not running)
│ Pre-built   │  RAM Usage: 0 MB
└─────────────┘
       ↓
┌─────────────┐
│ ff workflow │  CLI detects required worker
│ run         │  via /workflows/{name}/worker-info API
└─────────────┘
       ↓
┌─────────────┐
│ docker      │  docker start fuzzforge-worker-ossfuzz
│ start       │  Wait for healthy status
└─────────────┘
       ↓
┌─────────────┐
│ Worker      │  Status: Up
│ Running     │  RAM Usage: ~1-2 GB
└─────────────┘
```

### Resource Savings

| State | Services Running | RAM Usage |
|-------|-----------------|-----------|
| **Idle** (no workflows) | Temporal, PostgreSQL, MinIO, Backend | ~1.2 GB |
| **Active** (1 workflow) | Core + 1 worker | ~3-5 GB |
| **Legacy** (all workers) | Core + all 5 workers | ~8 GB |

**Savings: ~6-7GB RAM when idle** ✨

### Configuration

Control via `.fuzzforge/config.yaml`:

```yaml
workers:
  auto_start_workers: true    # Auto-start when needed
  auto_stop_workers: false    # Auto-stop after completion
  worker_startup_timeout: 60  # Startup timeout (seconds)
  docker_compose_file: null   # Custom compose file path
```

Or via CLI flags:

```bash
# Auto-start disabled
ff workflow run ossfuzz_campaign . --no-auto-start

# Auto-stop enabled
ff workflow run ossfuzz_campaign . --wait --auto-stop
```

### Backend API

New endpoint: `GET /workflows/{workflow_name}/worker-info`

**Response**:
```json
{
  "workflow": "ossfuzz_campaign",
  "vertical": "ossfuzz",
  "worker_container": "fuzzforge-worker-ossfuzz",
  "task_queue": "ossfuzz-queue",
  "required": true
}
```

### SDK Integration

```python
from fuzzforge_sdk import FuzzForgeClient

client = FuzzForgeClient()
worker_info = client.get_workflow_worker_info("ossfuzz_campaign")
# Returns: {"vertical": "ossfuzz", "worker_container": "fuzzforge-worker-ossfuzz", ...}
```

### Manual Control

```bash
# Start worker manually
docker start fuzzforge-worker-ossfuzz

# Stop worker manually
docker stop fuzzforge-worker-ossfuzz

# Check all worker statuses
docker ps -a --filter "name=fuzzforge-worker"
```

---

## Level 1: Docker Container Limits (Primary)

Docker container limits are the **primary enforcement mechanism** for CPU and memory resources. These are configured in `docker-compose.yml` and enforced by the Docker runtime.

### Configuration

```yaml
services:
  worker-rust:
    deploy:
      resources:
        limits:
          cpus: '2.0'      # Maximum 2 CPU cores
          memory: 2G       # Maximum 2GB RAM
        reservations:
          cpus: '0.5'      # Minimum 0.5 CPU cores reserved
          memory: 512M     # Minimum 512MB RAM reserved
```

### How It Works

- **CPU Limit**: Docker throttles CPU usage when the container exceeds the limit
- **Memory Limit**: Docker kills the container (OOM) if it exceeds the memory limit
- **Reservations**: Guarantees minimum resources are available to the worker

### Example Configuration by Vertical

Different verticals have different resource needs:

**Rust Worker** (CPU-intensive fuzzing):
```yaml
worker-rust:
  deploy:
    resources:
      limits:
        cpus: '4.0'
        memory: 4G
```

**Android Worker** (Memory-intensive emulation):
```yaml
worker-android:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 8G
```

**Web Worker** (Lightweight analysis):
```yaml
worker-web:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
```

### Monitoring Container Resources

Check real-time resource usage:

```bash
# Monitor all workers
docker stats

# Monitor specific worker
docker stats fuzzforge-worker-rust

# Output:
# CONTAINER           CPU %    MEM USAGE / LIMIT     MEM %
# fuzzforge-worker-rust   85%     1.5GiB / 2GiB        75%
```

---

## Level 2: Worker Concurrency Limits

The `MAX_CONCURRENT_ACTIVITIES` environment variable controls how many workflows can execute **simultaneously** on a single worker.

### Configuration

```yaml
services:
  worker-rust:
    environment:
      MAX_CONCURRENT_ACTIVITIES: 5
    deploy:
      resources:
        limits:
          memory: 2G
```

### How It Works

- **Total Container Memory**: 2GB
- **Concurrent Workflows**: 5
- **Memory per Workflow**: ~400MB (2GB ÷ 5)

If a 6th workflow is submitted, it **waits in the Temporal queue** until one of the 5 running workflows completes.

### Calculating Concurrency

Use this formula to determine `MAX_CONCURRENT_ACTIVITIES`:

```
MAX_CONCURRENT_ACTIVITIES = Container Memory Limit / Estimated Workflow Memory
```

**Example:**
- Container limit: 4GB
- Workflow memory: ~800MB
- Concurrency: 4GB ÷ 800MB = **5 concurrent workflows**

### Configuration Examples

**High Concurrency (Lightweight Workflows)**:
```yaml
worker-web:
  environment:
    MAX_CONCURRENT_ACTIVITIES: 10  # Many small workflows
  deploy:
    resources:
      limits:
        memory: 2G  # ~200MB per workflow
```

**Low Concurrency (Heavy Workflows)**:
```yaml
worker-rust:
  environment:
    MAX_CONCURRENT_ACTIVITIES: 2  # Few large workflows
  deploy:
    resources:
      limits:
        memory: 4G  # ~2GB per workflow
```

### Monitoring Concurrency

Check how many workflows are running:

```bash
# View worker logs
docker-compose -f docker-compose.yml logs worker-rust | grep "Starting"

# Check Temporal UI
# Open http://localhost:8080
# Navigate to "Task Queues" → "rust" → See pending/running counts
```

---

## Level 3: Workflow Metadata (Advisory)

Workflow metadata in `metadata.yaml` documents resource requirements, but these are **advisory only** (except for timeout).

### Configuration

```yaml
# backend/toolbox/workflows/security_assessment/metadata.yaml
requirements:
  resources:
    memory: "512Mi"    # Estimated memory usage (advisory)
    cpu: "500m"        # Estimated CPU usage (advisory)
    timeout: 1800      # Execution timeout in seconds (ENFORCED)
```

### What's Enforced vs Advisory

| Field | Enforcement | Description |
|-------|-------------|-------------|
| `timeout` | ✅ **Enforced by Temporal** | Workflow killed if exceeds timeout |
| `memory` | ⚠️ Advisory only | Documents expected memory usage |
| `cpu` | ⚠️ Advisory only | Documents expected CPU usage |

### Why Metadata Is Useful

Even though `memory` and `cpu` are advisory, they're valuable for:

1. **Capacity Planning**: Determine appropriate container limits
2. **Concurrency Tuning**: Calculate `MAX_CONCURRENT_ACTIVITIES`
3. **Documentation**: Communicate resource needs to users
4. **Scheduling Hints**: Future horizontal scaling logic

### Timeout Enforcement

The `timeout` field is **enforced by Temporal**:

```python
# Temporal automatically cancels workflow after timeout
@workflow.defn
class SecurityAssessmentWorkflow:
    @workflow.run
    async def run(self, target_id: str):
        # If this takes longer than metadata.timeout (1800s),
        # Temporal will cancel the workflow
        ...
```

**Check timeout in Temporal UI:**
1. Open http://localhost:8080
2. Navigate to workflow execution
3. See "Timeout" in workflow details
4. If exceeded, status shows "TIMED_OUT"

---

## Resource Management Best Practices

### 1. Set Conservative Container Limits

Start with lower limits and increase based on actual usage:

```yaml
# Start conservative
worker-rust:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G

# Monitor with: docker stats
# Increase if consistently hitting limits
```

### 2. Calculate Concurrency from Profiling

Profile a single workflow first:

```bash
# Run single workflow and monitor
docker stats fuzzforge-worker-rust

# Note peak memory usage (e.g., 800MB)
# Calculate concurrency: 4GB ÷ 800MB = 5
```

### 3. Set Realistic Timeouts

Base timeouts on actual workflow duration:

```yaml
# Static analysis: 5-10 minutes
timeout: 600

# Fuzzing: 1-24 hours
timeout: 86400

# Quick scans: 1-2 minutes
timeout: 120
```

### 4. Monitor Resource Exhaustion

Watch for these warning signs:

```bash
# Check for OOM kills
docker-compose -f docker-compose.yml logs worker-rust | grep -i "oom\|killed"

# Check for CPU throttling
docker stats fuzzforge-worker-rust
# If CPU% consistently at limit → increase cpus

# Check for memory pressure
docker stats fuzzforge-worker-rust
# If MEM% consistently >90% → increase memory
```

### 5. Use Vertical-Specific Configuration

Different verticals have different needs:

| Vertical | CPU Priority | Memory Priority | Typical Config |
|----------|--------------|-----------------|----------------|
| Rust Fuzzing | High | Medium | 4 CPUs, 4GB RAM |
| Android Analysis | Medium | High | 2 CPUs, 8GB RAM |
| Web Scanning | Low | Low | 1 CPU, 1GB RAM |
| Static Analysis | Medium | Medium | 2 CPUs, 2GB RAM |

---

## Horizontal Scaling

To handle more workflows, scale worker containers horizontally:

```bash
# Scale rust worker to 3 instances
docker-compose -f docker-compose.yml up -d --scale worker-rust=3

# Now you can run:
# - 3 workers × 5 concurrent activities = 15 workflows simultaneously
```

**How it works:**
- Temporal load balances across all workers on the same task queue
- Each worker has independent resource limits
- No shared state between workers

---

## Troubleshooting Resource Issues

### Issue: Workflows Stuck in "Running" State

**Symptom:** Workflow shows RUNNING but makes no progress

**Diagnosis:**
```bash
# Check worker is alive
docker-compose -f docker-compose.yml ps worker-rust

# Check worker resource usage
docker stats fuzzforge-worker-rust

# Check for OOM kills
docker-compose -f docker-compose.yml logs worker-rust | grep -i oom
```

**Solution:**
- Increase memory limit if worker was killed
- Reduce `MAX_CONCURRENT_ACTIVITIES` if overloaded
- Check worker logs for errors

### Issue: "Too Many Pending Tasks"

**Symptom:** Temporal shows many queued workflows

**Diagnosis:**
```bash
# Check concurrent activities setting
docker exec fuzzforge-worker-rust env | grep MAX_CONCURRENT_ACTIVITIES

# Check current workload
docker-compose -f docker-compose.yml logs worker-rust | grep "Starting"
```

**Solution:**
- Increase `MAX_CONCURRENT_ACTIVITIES` if resources allow
- Add more worker instances (horizontal scaling)
- Increase container resource limits

### Issue: Workflow Timeout

**Symptom:** Workflow shows "TIMED_OUT" in Temporal UI

**Diagnosis:**
1. Check `metadata.yaml` timeout setting
2. Check Temporal UI for execution duration
3. Determine if timeout is appropriate

**Solution:**
```yaml
# Increase timeout in metadata.yaml
requirements:
  resources:
    timeout: 3600  # Increased from 1800
```

---

## Workspace Isolation and Cache Management

FuzzForge uses workspace isolation to prevent concurrent workflows from interfering with each other. Each workflow run can have its own isolated workspace or share a common workspace based on the isolation mode.

### Cache Directory Structure

Workers cache downloaded targets locally to avoid repeated downloads:

```
/cache/
├── {target_id_1}/
│   ├── {run_id_1}/        # Isolated mode
│   │   ├── target         # Downloaded tarball
│   │   └── workspace/     # Extracted files
│   ├── {run_id_2}/
│   │   ├── target
│   │   └── workspace/
│   └── workspace/         # Shared mode (no run_id)
│       └── ...
├── {target_id_2}/
│   └── shared/            # Copy-on-write shared download
│       ├── target
│       └── workspace/
```

### Isolation Modes

**Isolated Mode** (default for fuzzing):
- Each run gets `/cache/{target_id}/{run_id}/workspace/`
- Safe for concurrent execution
- Cleanup removes entire run directory

**Shared Mode** (for read-only workflows):
- All runs share `/cache/{target_id}/workspace/`
- Efficient (downloads once)
- No cleanup (cache persists)

**Copy-on-Write Mode**:
- Downloads to `/cache/{target_id}/shared/`
- Copies to `/cache/{target_id}/{run_id}/` per run
- Balances performance and isolation

### Cache Limits

Configure cache limits via environment variables:

```yaml
worker-rust:
  environment:
    CACHE_DIR: /cache
    CACHE_MAX_SIZE: 10GB    # Maximum cache size before LRU eviction
    CACHE_TTL: 7d           # Time-to-live for cached files
```

### LRU Eviction

When cache exceeds `CACHE_MAX_SIZE`, the least-recently-used files are automatically evicted:

1. Worker tracks last access time for each cached target
2. When cache is full, oldest accessed files are removed first
3. Eviction runs periodically (every 30 minutes)

### Monitoring Cache Usage

Check cache size and cleanup logs:

```bash
# Check cache size
docker exec fuzzforge-worker-rust du -sh /cache

# Monitor cache evictions
docker-compose -f docker-compose.yml logs worker-rust | grep "Evicted from cache"

# Check download vs cache hit rate
docker-compose -f docker-compose.yml logs worker-rust | grep -E "Cache (HIT|MISS)"
```

See the [Workspace Isolation](/docs/concept/workspace-isolation) guide for complete details on isolation modes and when to use each.

---

## Summary

FuzzForge's resource management strategy:

1. **Docker Container Limits**: Primary enforcement (CPU/memory hard limits)
2. **Concurrency Limits**: Controls parallel workflows per worker
3. **Workflow Metadata**: Advisory resource hints + enforced timeout
4. **Workspace Isolation**: Controls cache sharing and cleanup behavior

**Key Takeaways:**
- Set conservative Docker limits and adjust based on monitoring
- Calculate `MAX_CONCURRENT_ACTIVITIES` from container memory ÷ workflow memory
- Use `docker stats` and Temporal UI to monitor resource usage
- Scale horizontally by adding more worker instances
- Set realistic timeouts based on actual workflow duration
- Choose appropriate isolation mode (isolated for fuzzing, shared for analysis)
- Monitor cache usage and adjust `CACHE_MAX_SIZE` as needed

---

**Next Steps:**
- Review `docker-compose.yml` resource configuration
- Profile your workflows to determine actual resource usage
- Adjust limits based on monitoring data
- Set up alerts for resource exhaustion
