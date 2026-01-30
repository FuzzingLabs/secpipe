# FuzzForge AI Architecture

**Last Updated:** 2025-10-14
**Status:** Production - Temporal with Vertical Workers

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture (Temporal + Vertical Workers)](#current-architecture-temporal--vertical-workers)
3. [Vertical Worker Model](#vertical-worker-model)
4. [Storage Strategy (MinIO)](#storage-strategy-minio)
5. [Dynamic Workflow Loading](#dynamic-workflow-loading)
6. [Architecture Principles](#architecture-principles)
7. [Component Details](#component-details)
8. [Scaling Strategy](#scaling-strategy)
9. [File Lifecycle Management](#file-lifecycle-management)
10. [Future: Nomad Migration](#future-nomad-migration)

---

## Executive Summary

### The Architecture

**Temporal orchestration** with a **vertical worker architecture** where each worker is pre-built with domain-specific security toolchains (Android, Rust, Web, iOS, Blockchain, OSS-Fuzz, etc.). Uses **MinIO** for unified S3-compatible storage across dev and production environments.

### Key Architecture Features

1. **Vertical Specialization:** Pre-built toolchains (Android: Frida, apktool; Rust: AFL++, cargo-fuzz)
2. **Zero Startup Overhead:** Long-lived workers (no container spawn per workflow)
3. **Dynamic Workflows:** Add workflows without rebuilding images (mount as volume)
4. **Unified Storage:** MinIO works identically in dev and prod
5. **Better Security:** No host filesystem mounts, isolated uploaded targets
6. **Automatic Cleanup:** MinIO lifecycle policies handle file expiration
7. **Scalability:** Clear path from single-host to multi-host to Nomad cluster

---

## Current Architecture (Temporal + Vertical Workers)

### Infrastructure Overview

```
┌───────────────────────────────────────────────────────────────┐
│ FuzzForge Platform                                            │
│                                                                │
│  ┌──────────────────┐         ┌─────────────────────────┐   │
│  │ Temporal Server  │◄────────│ MinIO (S3 Storage)      │   │
│  │ - Workflows      │         │ - Uploaded targets      │   │
│  │ - State mgmt     │         │ - Results (optional)    │   │
│  │ - Task queues    │         │ - Lifecycle policies    │   │
│  └────────┬─────────┘         └─────────────────────────┘   │
│           │                                                    │
│           │ (Task queue routing)                              │
│           │                                                    │
│  ┌────────┴────────────────────────────────────────────────┐ │
│  │ Vertical Workers (Long-lived)                            │ │
│  │                                                          │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐│ │
│  │  │ Android       │  │ Rust/Native   │  │ Web/JS      ││ │
│  │  │ - apktool     │  │ - AFL++       │  │ - Node.js   ││ │
│  │  │ - Frida       │  │ - cargo-fuzz  │  │ - OWASP ZAP ││ │
│  │  │ - jadx        │  │ - gdb         │  │ - semgrep   ││ │
│  │  │ - MobSF       │  │ - valgrind    │  │ - eslint    ││ │
│  │  └───────────────┘  └───────────────┘  └─────────────┘│ │
│  │                                                          │ │
│  │  ┌───────────────┐  ┌───────────────┐                  │ │
│  │  │ iOS           │  │ Blockchain    │                  │ │
│  │  │ - class-dump  │  │ - mythril     │                  │ │
│  │  │ - Clutch      │  │ - slither     │                  │ │
│  │  │ - Frida       │  │ - echidna     │                  │ │
│  │  │ - Hopper      │  │ - manticore   │                  │ │
│  │  └───────────────┘  └───────────────┘                  │ │
│  │                                                          │ │
│  │  All workers have:                                       │ │
│  │  - /app/toolbox mounted (workflow code)                 │ │
│  │  - /cache for MinIO downloads                           │ │
│  │  - Dynamic workflow discovery at startup                │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### Service Breakdown

```yaml
services:
  temporal:         # Workflow orchestration + embedded SQLite (dev) or Postgres (prod)
  minio:            # S3-compatible storage for targets and results
  minio-setup:      # One-time: create buckets, set policies
  worker-android:   # Android security vertical (scales independently)
  worker-rust:      # Rust/native security vertical
  worker-web:       # Web security vertical
  # Additional verticals as needed: ios, blockchain, go, etc.

Total: 6+ services (scales with verticals)
```

### Resource Usage

```
Temporal:        ~500MB  (includes embedded DB in dev)
MinIO:           ~256MB  (with CI_CD=true flag)
MinIO-setup:     ~20MB   (ephemeral, exits after setup)
Worker-android:  ~512MB  (varies by toolchain)
Worker-rust:     ~512MB
Worker-web:      ~512MB
─────────────────────────
Total:           ~2.3GB

Note: +450MB overhead is worth it for:
  - Unified dev/prod architecture
  - No host filesystem mounts (security)
  - Auto cleanup (lifecycle policies)
  - Multi-host ready
```

---

## Vertical Worker Model

### Concept

Instead of generic workers that spawn workflow-specific containers, we have **specialized long-lived workers** pre-built with complete security toolchains for specific domains.

### Vertical Taxonomy

| Vertical | Tools Included | Use Cases | Workflows |
|----------|---------------|-----------|-----------|
| **android** | apktool, jadx, Frida, MobSF, androguard | APK analysis, reverse engineering, dynamic instrumentation | APK security assessment, malware analysis, repackaging detection |
| **rust** | AFL++, cargo-fuzz, gdb, valgrind, AddressSanitizer | Native fuzzing, memory safety | Cargo fuzzing campaigns, binary analysis |
| **web** | Node.js, OWASP ZAP, Burp Suite, semgrep, eslint | Web app security testing | XSS detection, SQL injection scanning, API fuzzing |
| **ios** | class-dump, Clutch, Frida, Hopper, ios-deploy | iOS app analysis | IPA analysis, jailbreak detection, runtime hooking |
| **blockchain** | mythril, slither, echidna, manticore, solc | Smart contract security | Solidity static analysis, property-based fuzzing |
| **go** | go-fuzz, staticcheck, gosec, dlv | Go security testing | Go fuzzing, static analysis |

### Vertical Worker Architecture

```dockerfile
# Example: workers/android/Dockerfile
FROM python:3.11-slim

# Install Android SDK and tools
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk \
    android-sdk \
    && rm -rf /var/lib/apt/lists/*

# Install security tools
RUN pip install --no-cache-dir \
    apktool \
    androguard \
    frida-tools \
    pyaxmlparser

# Install MobSF dependencies
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Temporal Python SDK
RUN pip install --no-cache-dir \
    temporalio \
    boto3 \
    pydantic

# Copy worker entrypoint
COPY worker.py /app/
WORKDIR /app

# Worker will mount /app/toolbox and discover workflows at runtime
CMD ["python", "worker.py"]
```

### Dynamic Workflow Discovery

```python
# workers/android/worker.py
import asyncio
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Worker

async def discover_workflows(vertical: str):
    """Discover workflows for this vertical from mounted toolbox"""
    workflows = []
    toolbox = Path("/app/toolbox/workflows")

    for workflow_dir in toolbox.iterdir():
        if not workflow_dir.is_dir():
            continue

        metadata_file = workflow_dir / "metadata.yaml"
        if not metadata_file.exists():
            continue

        # Parse metadata
        with open(metadata_file) as f:
            metadata = yaml.safe_load(f)

        # Check if workflow is for this vertical
        if metadata.get("vertical") == vertical:
            # Dynamically import workflow module
            workflow_module = f"toolbox.workflows.{workflow_dir.name}.workflow"
            module = __import__(workflow_module, fromlist=[''])

            # Find @workflow.defn decorated classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, '__temporal_workflow_definition'):
                    workflows.append(obj)
                    logger.info(f"Discovered workflow: {name} for vertical {vertical}")

    return workflows

async def main():
    vertical = os.getenv("WORKER_VERTICAL", "android")
    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")

    # Discover workflows for this vertical
    workflows = await discover_workflows(vertical)

    if not workflows:
        logger.warning(f"No workflows found for vertical: {vertical}")
        return

    # Connect to Temporal
    client = await Client.connect(temporal_address)

    # Start worker with discovered workflows
    worker = Worker(
        client,
        task_queue=f"{vertical}-queue",
        workflows=workflows,
        activities=[
            get_target_activity,
            cleanup_cache_activity,
            # ... vertical-specific activities
        ]
    )

    logger.info(f"Worker started for vertical '{vertical}' with {len(workflows)} workflows")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Workflow Declaration

```yaml
# toolbox/workflows/android_apk_analysis/metadata.yaml
name: android_apk_analysis
version: 1.0.0
description: "Deep analysis of Android APK files"
vertical: android  # ← Routes to worker-android
dependencies:
  python:
    - androguard==4.1.0  # Additional Python deps (optional)
    - pyaxmlparser==0.3.28
```

```python
# toolbox/workflows/android_apk_analysis/workflow.py
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class AndroidApkAnalysisWorkflow:
    """
    Comprehensive Android APK security analysis
    Runs in worker-android with apktool, Frida, jadx pre-installed
    """

    @workflow.run
    async def run(self, target_id: str) -> dict:
        # Activity 1: Download target from MinIO
        apk_path = await workflow.execute_activity(
            "get_target",
            target_id,
            start_to_close_timeout=timedelta(minutes=5)
        )

        # Activity 2: Extract manifest (uses apktool - pre-installed)
        manifest = await workflow.execute_activity(
            "extract_manifest",
            apk_path,
            start_to_close_timeout=timedelta(minutes=5)
        )

        # Activity 3: Static analysis (uses jadx - pre-installed)
        static_results = await workflow.execute_activity(
            "static_analysis",
            apk_path,
            start_to_close_timeout=timedelta(minutes=30)
        )

        # Activity 4: Frida instrumentation (uses Frida - pre-installed)
        dynamic_results = await workflow.execute_activity(
            "dynamic_analysis",
            apk_path,
            start_to_close_timeout=timedelta(hours=2)
        )

        # Activity 5: Cleanup local cache
        await workflow.execute_activity(
            "cleanup_cache",
            apk_path,
            start_to_close_timeout=timedelta(minutes=1)
        )

        return {
            "manifest": manifest,
            "static": static_results,
            "dynamic": dynamic_results
        }
```

---

## Storage Strategy (MinIO)

### Why MinIO?

**Goal:** Unified storage that works identically in dev and production, eliminating environment-specific code.

**Alternatives considered:**
1. ❌ **LocalVolumeStorage** (mount /Users, /home): Security risk, platform-specific, doesn't scale
2. ❌ **Different storage per environment**: Complex, error-prone, dual maintenance
3. ✅ **MinIO everywhere**: Lightweight (+256MB), S3-compatible, multi-host ready

### MinIO Configuration

```yaml
# docker-compose.yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"   # S3 API
      - "9001:9001"   # Web Console (http://localhost:9001)
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: fuzzforge
      MINIO_ROOT_PASSWORD: fuzzforge123
      MINIO_CI_CD: "true"  # Reduces memory to 256MB (from 1GB)
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 5

  # One-time setup: create buckets and set lifecycle policies
  minio-setup:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set fuzzforge http://minio:9000 fuzzforge fuzzforge123;
      mc mb fuzzforge/targets --ignore-existing;
      mc mb fuzzforge/results --ignore-existing;
      mc ilm add fuzzforge/targets --expiry-days 7;
      mc anonymous set download fuzzforge/results;
      "
```

### Storage Backend Implementation

```python
# backend/src/storage/s3_cached.py
import boto3
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class S3CachedStorage:
    """
    S3-compatible storage with local caching.
    Works with MinIO (dev/prod) or AWS S3 (cloud).
    """

    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=os.getenv('S3_ENDPOINT', 'http://minio:9000'),
            aws_access_key_id=os.getenv('S3_ACCESS_KEY', 'fuzzforge'),
            aws_secret_access_key=os.getenv('S3_SECRET_KEY', 'fuzzforge123')
        )
        self.bucket = os.getenv('S3_BUCKET', 'targets')
        self.cache_dir = Path(os.getenv('CACHE_DIR', '/cache'))
        self.cache_max_size = self._parse_size(os.getenv('CACHE_MAX_SIZE', '10GB'))
        self.cache_ttl = self._parse_duration(os.getenv('CACHE_TTL', '7d'))

    async def upload_target(self, file_path: Path, user_id: str) -> str:
        """Upload target to MinIO and return target ID"""
        target_id = str(uuid4())

        # Upload with metadata for lifecycle management
        self.s3.upload_file(
            str(file_path),
            self.bucket,
            f'{target_id}/target',
            ExtraArgs={
                'Metadata': {
                    'user_id': user_id,
                    'uploaded_at': datetime.now().isoformat(),
                    'filename': file_path.name
                }
            }
        )

        logger.info(f"Uploaded target {target_id} ({file_path.name})")
        return target_id

    async def get_target(self, target_id: str) -> Path:
        """
        Get target from cache or download from MinIO.
        Returns local path to cached file.
        """
        cache_path = self.cache_dir / target_id
        cached_file = cache_path / "target"

        # Check cache
        if cached_file.exists():
            # Update access time for LRU
            cached_file.touch()
            logger.info(f"Cache hit: {target_id}")
            return cached_file

        # Cache miss - download from MinIO
        logger.info(f"Cache miss: {target_id}, downloading from MinIO")
        cache_path.mkdir(parents=True, exist_ok=True)

        self.s3.download_file(
            self.bucket,
            f'{target_id}/target',
            str(cached_file)
        )

        return cached_file

    async def cleanup_cache(self):
        """LRU eviction when cache exceeds max size"""
        cache_files = []
        total_size = 0

        for cache_file in self.cache_dir.rglob('*'):
            if cache_file.is_file():
                stat = cache_file.stat()
                cache_files.append({
                    'path': cache_file,
                    'size': stat.st_size,
                    'atime': stat.st_atime
                })
                total_size += stat.st_size

        if total_size > self.cache_max_size:
            # Sort by access time (oldest first)
            cache_files.sort(key=lambda x: x['atime'])

            for file_info in cache_files:
                if total_size <= self.cache_max_size:
                    break

                file_info['path'].unlink()
                total_size -= file_info['size']
                logger.info(f"Evicted from cache: {file_info['path']}")
```

### Performance Characteristics

| Operation | Direct Filesystem | MinIO (Local) | Impact |
|-----------|------------------|---------------|---------|
| Small file (<1MB) | ~1ms | ~5-10ms | Negligible for security workflows |
| Large file (>100MB) | ~200ms | ~220ms | ~10% overhead |
| Workflow duration | 5-60 minutes | 5-60 minutes + 2-4s upload | <1% overhead |
| Subsequent scans | Same | **Cached (0ms)** | Better than filesystem |

**Verdict:** 2-4 second upload overhead is **negligible** for workflows that run 5-60 minutes.

### Workspace Isolation

To support concurrent workflows safely, FuzzForge implements workspace isolation with three modes:

**1. Isolated Mode (Default)**
```python
# Each workflow run gets its own workspace
cache_path = f"/cache/{target_id}/{run_id}/workspace/"
```

- **Use for:** Fuzzing workflows that modify files (corpus, crashes)
- **Advantages:** Safe for concurrent execution, no file conflicts
- **Cleanup:** Entire run directory removed after workflow completes

**2. Shared Mode**
```python
# All runs share the same workspace
cache_path = f"/cache/{target_id}/workspace/"
```

- **Use for:** Read-only analysis workflows (security scanning, static analysis)
- **Advantages:** Efficient (downloads once), lower bandwidth/storage
- **Cleanup:** No cleanup (workspace persists for reuse)

**3. Copy-on-Write Mode**
```python
# Download once to shared location, copy per run
shared_cache = f"/cache/{target_id}/shared/workspace/"
run_cache = f"/cache/{target_id}/{run_id}/workspace/"
```

- **Use for:** Large targets that need isolation
- **Advantages:** Download once, isolated per-run execution
- **Cleanup:** Run-specific copies removed, shared cache persists

**Configuration:**

Workflows specify isolation mode in `metadata.yaml`:
```yaml
name: atheris_fuzzing
workspace_isolation: "isolated"  # or "shared" or "copy-on-write"
```

Workers automatically handle download, extraction, and cleanup based on the mode.

---

## Dynamic Workflow Loading

### The Problem

**Requirement:** Workflows must be dynamically added without modifying the codebase or rebuilding Docker images.

**Traditional approach (doesn't work):**
- Build Docker image per workflow with dependencies
- Push to registry
- Worker pulls and spawns container
- ❌ Requires rebuild for every workflow change
- ❌ Registry overhead
- ❌ Slow (5-10s startup per workflow)

**Our approach (works):**
- Workflow code mounted as volume into long-lived workers
- Workers scan `/app/toolbox/workflows` at startup
- Dynamically import and register workflows matching vertical
- ✅ No rebuild needed
- ✅ No registry
- ✅ Zero startup overhead

### Implementation

**1. Docker Compose volume mount:**
```yaml
worker-android:
  volumes:
    - ./toolbox:/app/toolbox:ro  # Mount workflow code as read-only
```

**2. Worker discovers workflows:**
```python
# Runs at worker startup
for workflow_dir in Path("/app/toolbox/workflows").iterdir():
    metadata = yaml.safe_load((workflow_dir / "metadata.yaml").read_text())

    # Only load workflows for this vertical
    if metadata.get("vertical") == os.getenv("WORKER_VERTICAL"):
        # Dynamically import workflow.py
        module = importlib.import_module(f"toolbox.workflows.{workflow_dir.name}.workflow")

        # Find @workflow.defn classes
        workflows.append(module.MyWorkflowClass)
```

**3. Developer adds workflow:**
```bash
# 1. Create workflow directory
mkdir -p toolbox/workflows/my_new_workflow

# 2. Write metadata
cat > toolbox/workflows/my_new_workflow/metadata.yaml <<EOF
vertical: android
EOF

# 3. Write workflow
cat > toolbox/workflows/my_new_workflow/workflow.py <<EOF
from temporalio import workflow

@workflow.defn
class MyNewWorkflow:
    @workflow.run
    async def run(self, target_id: str):
        # Implementation
        pass
EOF

# 4. Restart worker to pick up new workflow
docker-compose restart worker-android

# Done! No image building, no registry push
```

### Hot Reload (Optional Advanced Feature)

```python
# Worker watches /app/toolbox for file changes
import watchdog

observer = Observer()
observer.schedule(WorkflowReloadHandler(), "/app/toolbox/workflows", recursive=True)
observer.start()

class WorkflowReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            logger.info(f"Detected workflow change: {event.src_path}")
            # Reload workflow without restarting worker
            reload_workflows()
```

---

## Architecture Principles

### 1. Vertical Specialization

**Principle:** Each worker is specialized for a security domain with pre-built toolchains.

**Benefits:**
- Faster workflow execution (tools already installed)
- Better resource utilization (long-lived workers)
- Clear marketing positioning (sell verticals, not orchestration)
- Easier development (known toolchain per vertical)

### 2. Unified Storage

**Principle:** Same storage backend (MinIO) in development and production.

**Benefits:**
- No environment-specific code
- Easier testing (dev = prod)
- Multi-host ready from day one
- Better security (no host mounts)

### 3. Dynamic Workflow Discovery

**Principle:** Workflows are discovered and loaded at runtime, not compile-time.

**Benefits:**
- Add workflows without rebuilding images
- No registry overhead
- Faster iteration for developers
- Supports user-contributed workflows

### 4. Environment-Driven Configuration

**Principle:** All configuration via environment variables, no hardcoded values.

**Required Variables:**
```bash
# Worker configuration
TEMPORAL_ADDRESS=temporal:7233
WORKER_VERTICAL=android
MAX_CONCURRENT_ACTIVITIES=5

# Storage configuration
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=fuzzforge
S3_SECRET_KEY=fuzzforge123
S3_BUCKET=targets

# Cache configuration
CACHE_DIR=/cache
CACHE_MAX_SIZE=10GB
CACHE_TTL=7d
```

### 5. Fail-Safe Defaults

**Principle:** System works out-of-the-box with sensible defaults.

**Examples:**
- MinIO CI_CD mode (lightweight for dev)
- 7-day lifecycle policy (auto-cleanup)
- 10GB cache limit (prevent disk exhaustion)
- Embedded SQLite for Temporal (no Postgres in dev)

---

## Component Details

### Temporal Server

**Deployment Options:**

| Environment | Database | Memory | Notes |
|-------------|----------|--------|-------|
| Development | SQLite (embedded) | 500MB | Simple, no external DB |
| Production | PostgreSQL | 2GB | Clustered for HA |

**Configuration:**
```yaml
temporal:
  image: temporalio/auto-setup:latest
  ports:
    - "7233:7233"  # gRPC
    - "8233:8233"  # Web UI
  environment:
    - DB=sqlite  # or postgresql for prod
    - SQLITE_PRAGMA_journal_mode=WAL
```

### MinIO

**Resource Usage:**
- Memory: 256MB (CI_CD mode) to 1GB (production)
- CPU: Minimal (I/O bound)
- Disk: Depends on usage (recommend 100GB+)

**Configuration:**
```yaml
minio:
  image: minio/minio:latest
  environment:
    MINIO_CI_CD: "true"  # Lightweight mode
    MINIO_ROOT_USER: fuzzforge
    MINIO_ROOT_PASSWORD: fuzzforge123
```

**Web Console:** http://localhost:9001

### Vertical Workers

**Base Requirements:**
- Python 3.11+
- Temporal Python SDK
- boto3 (S3 client)
- Domain-specific tools

**Scaling:**
```yaml
# Scale vertically (more concurrent activities per worker)
environment:
  MAX_CONCURRENT_ACTIVITIES: 10  # Default: 5

# Scale horizontally (more workers)
docker-compose up -d --scale worker-android=3
```

---

## Scaling Strategy

### Phase 1: Single Host (Now - 6 months)

**Configuration:**
```yaml
# 1 Temporal + 1 MinIO + 3-5 vertical workers
# Capacity: 15-50 concurrent workflows
# Cost: ~$430/month
```

**When to move to Phase 2:** Saturating single host (CPU >80%, memory >90%)

### Phase 2: Multi-Host (6-18 months)

**Configuration:**
```
Host 1: Temporal + MinIO
Host 2: 5× worker-android
Host 3: 5× worker-rust
Host 4: 5× worker-web
```

**Changes required:**
```yaml
# Point all workers to central Temporal/MinIO
environment:
  TEMPORAL_ADDRESS: temporal.prod.fuzzforge.ai:7233
  S3_ENDPOINT: http://minio.prod.fuzzforge.ai:9000
```

**Capacity:** 3× Phase 1 = 45-150 concurrent workflows

### Phase 3: Nomad Cluster (18+ months, if needed)

**Trigger Points:**
- Managing 10+ hosts manually
- Need auto-scaling based on queue depth
- Need multi-tenancy (customer namespaces)

**Migration effort:** 1-2 weeks (workers unchanged, just change deployment method)

---

## File Lifecycle Management

### Automatic Cleanup via MinIO Lifecycle Policies

```bash
# Set on bucket (done by minio-setup service)
mc ilm add fuzzforge/targets --expiry-days 7

# MinIO automatically deletes objects older than 7 days
```

### Local Cache Eviction (LRU)

```python
# Worker background task (runs every 30 minutes)
async def cleanup_cache_task():
    while True:
        await storage.cleanup_cache()  # LRU eviction
        await asyncio.sleep(1800)  # 30 minutes
```

### Manual Deletion (API)

```python
@app.delete("/api/targets/{target_id}")
async def delete_target(target_id: str):
    """Allow users to manually delete uploaded targets"""
    s3.delete_object(Bucket='targets', Key=f'{target_id}/target')
    return {"status": "deleted"}
```

### Retention Policies

| Object Type | Default TTL | Configurable | Notes |
|-------------|-------------|--------------|-------|
| Uploaded targets | 7 days | Yes (env var) | Auto-deleted by MinIO |
| Worker cache | LRU (10GB limit) | Yes | Evicted when cache full |
| Workflow results | 30 days (optional) | Yes | Can store in MinIO |

---

## Future: Nomad Migration

### When to Add Nomad?

**Trigger points:**
- Managing 10+ hosts manually becomes painful
- Need auto-scaling based on queue depth
- Need multi-tenancy with resource quotas
- Want sophisticated scheduling (bin-packing, affinity rules)

**Estimated timing:** 18-24 months

### Migration Complexity

**Effort:** 1-2 weeks

**What changes:**
- Deployment method (docker-compose → Nomad jobs)
- Orchestration layer (manual → Nomad scheduler)

**What stays the same:**
- Worker Docker images (unchanged)
- Workflows (unchanged)
- Temporal (unchanged)
- MinIO (unchanged)
- Storage backend (unchanged)

### Nomad Job Example

```hcl
job "fuzzforge-worker-android" {
  datacenters = ["dc1"]
  type = "service"

  group "workers" {
    count = 5  # Auto-scales based on queue depth

    scaling {
      min = 1
      max = 20

      policy {
        evaluation_interval = "30s"

        check "queue_depth" {
          source = "prometheus"
          query  = "temporal_queue_depth{queue='android-queue'}"

          strategy "target-value" {
            target = 10  # Scale up if >10 tasks queued
          }
        }
      }
    }

    task "worker" {
      driver = "docker"

      config {
        image = "fuzzforge/worker-android:latest"

        volumes = [
          "/opt/fuzzforge/toolbox:/app/toolbox:ro"
        ]
      }

      env {
        TEMPORAL_ADDRESS = "temporal.service.consul:7233"
        WORKER_VERTICAL  = "android"
        S3_ENDPOINT      = "http://minio.service.consul:9000"
      }

      resources {
        cpu    = 500  # MHz
        memory = 512  # MB
      }
    }
  }
}
```

### Licensing Considerations

**Nomad BSL 1.1 Risk:** Depends on FuzzForge positioning

**Safe positioning (LOW risk):**
- ✅ Market as "Android/Rust/Web security verticals"
- ✅ Emphasize domain expertise, not orchestration
- ✅ Nomad is internal infrastructure
- ✅ Customers buy security services, not Nomad

**Risky positioning (MEDIUM risk):**
- ⚠️ Market as "generic workflow orchestration platform"
- ⚠️ Emphasize flexibility over domain expertise
- ⚠️ Could be seen as competing with HashiCorp

**Mitigation:**
- Keep marketing focused on security verticals
- Get legal review before Phase 3
- Alternative: Use Kubernetes (Apache 2.0, zero risk)

---

## Migration Timeline

### Phase 1: Foundation (Weeks 1-2)
- ✅ Create feature branch
- Set up Temporal docker-compose
- Add MinIO service
- Implement S3CachedStorage backend
- Create cleanup/lifecycle logic

### Phase 2: First Vertical Worker (Weeks 3-4)
- Design worker base template
- Create worker-rust with AFL++, cargo-fuzz
- Implement dynamic workflow discovery
- Test workflow loading from mounted volume

### Phase 3: Migrate Workflows (Weeks 5-6)
- Port security_assessment workflow to Temporal
- Update workflow metadata format
- Test end-to-end flow (upload → analyze → results)
- Verify cleanup/lifecycle

### Phase 4: Additional Verticals (Weeks 7-8)
- Create worker-android, worker-web
- Document vertical development guide
- Update CLI for MinIO uploads
- Update backend API for Temporal

### Phase 5: Testing & Docs (Weeks 9-10)
- Comprehensive testing
- Update README
- Migration guide for existing users
- Troubleshooting documentation

**Total: 10 weeks, rollback possible at any phase**

---

## Decision Log

### 2025-09-30: Architecture Implementation
- **Decision:** Temporal with Vertical Workers
- **Rationale:** Simpler infrastructure, better reliability, clear scaling path

### 2025-10-01: Vertical Worker Model
- **Decision:** Use long-lived vertical workers instead of ephemeral per-workflow containers
- **Rationale:**
  - Zero startup overhead (5s saved per workflow)
  - Pre-built toolchains (Android, Rust, Web, etc.)
  - Dynamic workflows via mounted volumes (no image rebuild)
  - Better marketing (sell verticals, not orchestration)
  - Safer Nomad BSL positioning

### 2025-10-01: Unified MinIO Storage
- **Decision:** Use MinIO for both dev and production (no LocalVolumeStorage)
- **Rationale:**
  - Unified codebase (no environment-specific code)
  - Lightweight (256MB with CI_CD=true)
  - Negligible overhead (2-4s for 250MB upload)
  - Better security (no host filesystem mounts)
  - Multi-host ready
  - Automatic cleanup via lifecycle policies

### 2025-10-01: Dynamic Workflow Loading
- **Decision:** Mount workflow code as volume, discover at runtime
- **Rationale:**
  - Add workflows without rebuilding images
  - No registry overhead
  - Supports user-contributed workflows
  - Faster iteration for developers

---

**Document Version:** 2.0
**Last Updated:** 2025-10-01
**Next Review:** After Phase 1 implementation (2 weeks)
