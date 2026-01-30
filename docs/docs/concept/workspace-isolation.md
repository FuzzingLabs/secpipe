# Workspace Isolation

FuzzForge's workspace isolation system ensures that concurrent workflow runs don't interfere with each other. This is critical for fuzzing and security analysis workloads where multiple workflows might process the same target simultaneously.

---

## Why Workspace Isolation?

### The Problem

Without isolation, concurrent workflows accessing the same target would share the same cache directory:

```
/cache/{target_id}/workspace/
```

This causes problems when:
- **Fuzzing workflows** modify corpus files and crash artifacts
- **Multiple runs** operate on the same target simultaneously
- **File conflicts** occur during read/write operations

### The Solution

FuzzForge implements configurable workspace isolation with three modes:

1. **isolated** (default): Each run gets its own workspace
2. **shared**: All runs share the same workspace
3. **copy-on-write**: Download once, copy per run

---

## Isolation Modes

### Isolated Mode (Default)

**Use for**: Fuzzing workflows, any workflow that modifies files

**Cache path**: `/cache/{target_id}/{run_id}/workspace/`

Each workflow run gets a completely isolated workspace directory. The target is downloaded to a run-specific path using the unique `run_id`.

**Advantages:**
- ✅ Safe for concurrent execution
- ✅ No file conflicts
- ✅ Clean per-run state

**Disadvantages:**
- ⚠️ Downloads target for each run (higher bandwidth/storage)
- ⚠️ No sharing of downloaded artifacts

**Example workflows:**
- `atheris_fuzzing` - Modifies corpus, creates crash files
- `cargo_fuzzing` - Modifies corpus, generates artifacts

**metadata.yaml:**
```yaml
name: atheris_fuzzing
workspace_isolation: "isolated"
```

**Cleanup behavior:**
Entire run directory `/cache/{target_id}/{run_id}/` is removed after workflow completes.

---

### Shared Mode

**Use for**: Read-only analysis workflows, security scanners

**Cache path**: `/cache/{target_id}/workspace/`

All workflow runs for the same target share a single workspace directory. The target is downloaded once and reused across runs.

**Advantages:**
- ✅ Efficient (download once, use many times)
- ✅ Lower bandwidth and storage usage
- ✅ Faster startup (cache hit after first download)

**Disadvantages:**
- ⚠️ Not safe for workflows that modify files
- ⚠️ Potential race conditions if workflows write

**Example workflows:**
- `security_assessment` - Read-only file scanning and analysis
- `secret_detection` - Read-only secret scanning

**metadata.yaml:**
```yaml
name: security_assessment
workspace_isolation: "shared"
```

**Cleanup behavior:**
No cleanup (workspace shared across runs). Cache persists until LRU eviction.

---

### Copy-on-Write Mode

**Use for**: Workflows that need isolation but benefit from shared initial download

**Cache paths**:
- Shared download: `/cache/{target_id}/shared/target`
- Per-run copy: `/cache/{target_id}/{run_id}/workspace/`

Target is downloaded once to a shared location, then copied for each run.

**Advantages:**
- ✅ Download once (shared bandwidth)
- ✅ Isolated per-run workspace (safe for modifications)
- ✅ Balances performance and safety

**Disadvantages:**
- ⚠️ Copy overhead (disk I/O per run)
- ⚠️ Higher storage usage than shared mode

**metadata.yaml:**
```yaml
name: my_workflow
workspace_isolation: "copy-on-write"
```

**Cleanup behavior:**
Run-specific copies removed, shared download persists until LRU eviction.

---

## How It Works

### Activity Signature

The `get_target` activity accepts isolation parameters:

```python
from temporalio import workflow

# In your workflow
target_path = await workflow.execute_activity(
    "get_target",
    args=[target_id, run_id, "isolated"],  # target_id, run_id, workspace_isolation
    start_to_close_timeout=timedelta(minutes=5)
)
```

### Path Resolution

Based on the isolation mode:

```python
# Isolated mode
if workspace_isolation == "isolated":
    cache_path = f"/cache/{target_id}/{run_id}/"

# Shared mode
elif workspace_isolation == "shared":
    cache_path = f"/cache/{target_id}/"

# Copy-on-write mode
else:  # copy-on-write
    shared_path = f"/cache/{target_id}/shared/"
    cache_path = f"/cache/{target_id}/{run_id}/"
    # Download to shared_path, copy to cache_path
```

### Cleanup

The `cleanup_cache` activity respects isolation mode:

```python
await workflow.execute_activity(
    "cleanup_cache",
    args=[target_path, "isolated"],  # target_path, workspace_isolation
    start_to_close_timeout=timedelta(minutes=1)
)
```

**Cleanup behavior by mode:**
- `isolated`: Removes `/cache/{target_id}/{run_id}/` entirely
- `shared`: Skips cleanup (shared across runs)
- `copy-on-write`: Removes run directory, keeps shared cache

---

## Cache Management

### Cache Directory Structure

```
/cache/
├── {target_id_1}/
│   ├── {run_id_1}/
│   │   ├── target        # Downloaded tarball
│   │   └── workspace/    # Extracted files
│   ├── {run_id_2}/
│   │   ├── target
│   │   └── workspace/
│   └── workspace/        # Shared mode (no run_id subdirectory)
│       └── ...
├── {target_id_2}/
│   └── shared/
│       ├── target        # Copy-on-write shared download
│       └── workspace/
```

### LRU Eviction

When cache exceeds the configured limit (default: 10GB), least-recently-used files are evicted automatically.

**Configuration:**
```yaml
# In worker environment
CACHE_DIR: /cache
CACHE_MAX_SIZE: 10GB
CACHE_TTL: 7d
```

**Eviction policy:**
- Tracks last access time for each cached target
- When cache is full, removes oldest accessed files first
- Cleanup runs periodically (every 30 minutes)

---

## Choosing the Right Mode

### Decision Matrix

| Workflow Type | Modifies Files? | Concurrent Runs? | Recommended Mode |
|---------------|----------------|------------------|------------------|
| Fuzzing (AFL, libFuzzer, Atheris) | ✅ Yes | ✅ Yes | **isolated** |
| Static Analysis | ❌ No | ✅ Yes | **shared** |
| Secret Scanning | ❌ No | ✅ Yes | **shared** |
| File Modification | ✅ Yes | ❌ No | **isolated** |
| Large Downloads | ❌ No | ✅ Yes | **copy-on-write** |

### Guidelines

**Use `isolated` when:**
- Workflow modifies files (corpus, crashes, logs)
- Fuzzing or dynamic analysis
- Concurrent runs must not interfere

**Use `shared` when:**
- Workflow only reads files
- Static analysis or scanning
- Want to minimize bandwidth/storage

**Use `copy-on-write` when:**
- Workflow modifies files but target is large (>100MB)
- Want isolation but minimize download overhead
- Balance between shared and isolated

---

## Configuration

### In Workflow Metadata

Document the isolation mode in `metadata.yaml`:

```yaml
name: atheris_fuzzing
version: "1.0.0"
vertical: python

# Workspace isolation mode
# - "isolated" (default): Each run gets own workspace
# - "shared": All runs share workspace (read-only workflows)
# - "copy-on-write": Download once, copy per run
workspace_isolation: "isolated"
```

### In Workflow Code

Pass isolation mode to storage activities:

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, target_id: str) -> Dict[str, Any]:
        # Get run ID for isolation
        run_id = workflow.info().run_id

        # Download target with isolation
        target_path = await workflow.execute_activity(
            "get_target",
            args=[target_id, run_id, "isolated"],
            start_to_close_timeout=timedelta(minutes=5)
        )

        # ... workflow logic ...

        # Cleanup with same isolation mode
        await workflow.execute_activity(
            "cleanup_cache",
            args=[target_path, "isolated"],
            start_to_close_timeout=timedelta(minutes=1)
        )
```

---

## Troubleshooting

### Issue: Workflows interfere with each other

**Symptom:** Fuzzing crashes from one run appear in another

**Diagnosis:**
```bash
# Check workspace paths in logs
docker logs fuzzforge-worker-python | grep "User code downloaded"

# Should see run-specific paths:
# ✅ /cache/abc-123/run-xyz-456/workspace  (isolated)
# ❌ /cache/abc-123/workspace              (shared - problem for fuzzing)
```

**Solution:** Change `workspace_isolation` to `"isolated"` in metadata.yaml

### Issue: High bandwidth usage

**Symptom:** Target downloaded repeatedly for same target_id

**Diagnosis:**
```bash
# Check MinIO downloads in logs
docker logs fuzzforge-worker-python | grep "downloading from MinIO"

# If many downloads for same target_id with shared workflow:
# Problem is using "isolated" mode for read-only workflow
```

**Solution:** Change to `"shared"` mode for read-only workflows

### Issue: Cache fills up quickly

**Symptom:** Disk space consumed by /cache directory

**Diagnosis:**
```bash
# Check cache size
docker exec fuzzforge-worker-python du -sh /cache

# Check LRU settings
docker exec fuzzforge-worker-python env | grep CACHE
```

**Solution:**
- Increase `CACHE_MAX_SIZE` environment variable
- Use `shared` mode for read-only workflows
- Decrease `CACHE_TTL` for faster eviction

---

## Summary

FuzzForge's workspace isolation system provides:

1. **Safe concurrent execution** for fuzzing and analysis workflows
2. **Three isolation modes** to balance safety vs efficiency
3. **Automatic cache management** with LRU eviction
4. **Per-workflow configuration** via metadata.yaml

**Key Takeaways:**
- Use `isolated` (default) for workflows that modify files
- Use `shared` for read-only analysis workflows
- Use `copy-on-write` to balance isolation and bandwidth
- Configure via `workspace_isolation` field in metadata.yaml
- Workers automatically handle download, extraction, and cleanup

---

**Next Steps:**
- Review your workflows and set appropriate isolation modes
- Monitor cache usage with `docker exec fuzzforge-worker-python du -sh /cache`
- Adjust `CACHE_MAX_SIZE` if needed for your workload
