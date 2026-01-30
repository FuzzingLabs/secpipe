# Debugging Workflows and Modules

This guide shows you how to debug FuzzForge workflows and modules using Temporal's powerful debugging features.

---

## Quick Debugging Checklist

When something goes wrong:

1. **Check worker logs** - `docker-compose -f docker-compose.yml logs worker-rust -f`
2. **Check Temporal UI** - http://localhost:8080 (visual execution history)
3. **Check MinIO console** - http://localhost:9001 (inspect uploaded files)
4. **Check backend logs** - `docker-compose -f docker-compose.yml logs fuzzforge-backend -f`

---

## Debugging Workflow Discovery

### Problem: Workflow Not Found

**Symptom:** Worker logs show "No workflows found for vertical: rust"

**Debug Steps:**

1. **Check if worker can see the workflow:**
   ```bash
   docker exec fuzzforge-worker-rust ls /app/toolbox/workflows/
   ```

2. **Check metadata.yaml exists:**
   ```bash
   docker exec fuzzforge-worker-rust cat /app/toolbox/workflows/my_workflow/metadata.yaml
   ```

3. **Verify vertical field matches:**
   ```bash
   docker exec fuzzforge-worker-rust grep "vertical:" /app/toolbox/workflows/my_workflow/metadata.yaml
   ```
   Should output: `vertical: rust`

4. **Check worker logs for discovery errors:**
   ```bash
   docker-compose -f docker-compose.yml logs worker-rust | grep "my_workflow"
   ```

**Solution:**
- Ensure `metadata.yaml` has correct `vertical` field
- Restart worker to reload: `docker-compose -f docker-compose.yml restart worker-rust`
- Check worker logs for discovery confirmation

---

## Debugging Workflow Execution

### Using Temporal Web UI

The Temporal UI at http://localhost:8080 is your primary debugging tool.

**Navigate to a workflow:**
1. Open http://localhost:8080
2. Click "Workflows" in left sidebar
3. Find your workflow by `run_id` or workflow name
4. Click to see detailed execution

**What you can see:**
- **Execution timeline** - When each activity started/completed
- **Input/output** - Exact parameters passed to workflow
- **Activity results** - Return values from each activity
- **Error stack traces** - Full Python tracebacks
- **Retry history** - All retry attempts with reasons
- **Worker information** - Which worker executed each activity

**Example: Finding why an activity failed:**
1. Open workflow in Temporal UI
2. Scroll to failed activity (marked in red)
3. Click on the activity
4. See full error message and stack trace
5. Check "Input" tab to see what parameters were passed

---

## Viewing Worker Logs

### Real-time Monitoring

```bash
# Follow logs from rust worker
docker-compose -f docker-compose.yml logs worker-rust -f

# Follow logs from all workers
docker-compose -f docker-compose.yml logs worker-rust worker-android -f

# Show last 100 lines
docker-compose -f docker-compose.yml logs worker-rust --tail 100
```

### What Worker Logs Show

**On startup:**
```
INFO: Scanning for workflows in: /app/toolbox/workflows
INFO: Importing workflow module: toolbox.workflows.security_assessment.workflow
INFO: ✓ Discovered workflow: SecurityAssessmentWorkflow from security_assessment (vertical: rust)
INFO: 🚀 Worker started for vertical 'rust'
```

**During execution:**
```
INFO: Starting SecurityAssessmentWorkflow (workflow_id=security_assessment-abc123, target_id=548193a1...)
INFO: Downloading target from MinIO: 548193a1-f73f-4ec1-8068-19ec2660b8e4
INFO: Executing activity: scan_files
INFO: Completed activity: scan_files (duration: 3.2s)
```

**On errors:**
```
ERROR: Failed to import workflow module toolbox.workflows.broken.workflow:
  File "/app/toolbox/workflows/broken/workflow.py", line 42
    def run(
IndentationError: expected an indented block
```

### Filtering Logs

```bash
# Show only errors
docker-compose -f docker-compose.yml logs worker-rust | grep ERROR

# Show workflow discovery
docker-compose -f docker-compose.yml logs worker-rust | grep "Discovered workflow"

# Show specific workflow execution
docker-compose -f docker-compose.yml logs worker-rust | grep "security_assessment-abc123"

# Show activity execution
docker-compose -f docker-compose.yml logs worker-rust | grep "activity"
```

---

## Debugging File Upload

### Check if File Was Uploaded

**Using MinIO Console:**
1. Open http://localhost:9001
2. Login: `fuzzforge` / `fuzzforge123`
3. Click "Buckets" → "targets"
4. Look for your `target_id` (UUID format)
5. Click to download and inspect locally

**Using CLI:**
```bash
# Check MinIO status
curl http://localhost:9000

# List backend logs for upload
docker-compose -f docker-compose.yml logs fuzzforge-backend | grep "upload"
```

### Check Worker Cache

```bash
# List cached targets
docker exec fuzzforge-worker-rust ls -lh /cache/

# Check specific target
docker exec fuzzforge-worker-rust ls -lh /cache/548193a1-f73f-4ec1-8068-19ec2660b8e4
```

---

## Interactive Debugging

### Access Running Worker

```bash
# Open shell in worker container
docker exec -it fuzzforge-worker-rust bash

# Now you can:
# - Check filesystem
ls -la /app/toolbox/workflows/

# - Test imports
python3 -c "from toolbox.workflows.my_workflow.workflow import MyWorkflow; print(MyWorkflow)"

# - Check environment variables
env | grep TEMPORAL

# - Test activities
cd /app/toolbox/workflows/my_workflow
python3 -c "from activities import my_activity; print(my_activity)"

# - Check cache
ls -lh /cache/
```

### Test Module in Isolation

```bash
# Enter worker container
docker exec -it fuzzforge-worker-rust bash

# Navigate to module
cd /app/toolbox/modules/scanner

# Run module directly
python3 -c "
from file_scanner import FileScannerModule
scanner = FileScannerModule()
print(scanner.get_metadata())
"
```

---

## Debugging Module Code

### Edit and Reload

Since toolbox is mounted as a volume, you can edit code on your host and reload:

1. **Edit module on host:**
   ```bash
   # On your host machine
   vim backend/toolbox/modules/scanner/file_scanner.py
   ```

2. **Restart worker to reload:**
   ```bash
   docker-compose -f docker-compose.yml restart worker-rust
   ```

3. **Check discovery logs:**
   ```bash
   docker-compose -f docker-compose.yml logs worker-rust | tail -50
   ```

### Add Debug Logging

Add logging to your workflow or module:

```python
import logging

logger = logging.getLogger(__name__)

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, target_id: str):
        workflow.logger.info(f"Starting with target_id: {target_id}")  # Shows in Temporal UI

        logger.info("Processing step 1")  # Shows in worker logs
        logger.debug(f"Debug info: {some_variable}")  # Shows if LOG_LEVEL=DEBUG

        try:
            result = await some_activity()
            logger.info(f"Activity result: {result}")
        except Exception as e:
            logger.error(f"Activity failed: {e}", exc_info=True)  # Full stack trace
            raise
```

Set debug logging:
```bash
# Edit docker-compose.yml
services:
  worker-rust:
    environment:
      LOG_LEVEL: DEBUG  # Change from INFO to DEBUG

# Restart
docker-compose -f docker-compose.yml restart worker-rust
```

---

## Common Issues and Solutions

### Issue: Workflow stuck in "Running" state

**Debug:**
1. Check Temporal UI for last completed activity
2. Check worker logs for errors
3. Check if worker is still running: `docker-compose -f docker-compose.yml ps worker-rust`

**Solution:**
- Worker may have crashed - restart it
- Activity may be hanging - check for infinite loops or stuck network calls
- Check worker resource limits: `docker stats fuzzforge-worker-rust`

### Issue: Import errors in workflow

**Debug:**
1. Check worker logs for full error trace
2. Check if module file exists:
   ```bash
   docker exec fuzzforge-worker-rust ls /app/toolbox/modules/my_module/
   ```

**Solution:**
- Ensure module is in correct directory
- Check for syntax errors: `docker exec fuzzforge-worker-rust python3 -m py_compile /app/toolbox/modules/my_module/my_module.py`
- Verify imports are correct

### Issue: Target file not found in worker

**Debug:**
1. Check if target exists in MinIO console
2. Check worker logs for download errors
3. Verify target_id is correct

**Solution:**
- Re-upload file via CLI
- Check MinIO is running: `docker-compose -f docker-compose.yml ps minio`
- Check MinIO credentials in worker environment

---

## Performance Debugging

### Check Activity Duration

**In Temporal UI:**
1. Open workflow execution
2. Scroll through activities
3. Each shows duration (e.g., "3.2s")
4. Identify slow activities

### Monitor Resource Usage

```bash
# Monitor worker resource usage
docker stats fuzzforge-worker-rust

# Check worker logs for memory warnings
docker-compose -f docker-compose.yml logs worker-rust | grep -i "memory\|oom"
```

### Profile Workflow Execution

Add timing to your workflow:

```python
import time

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, target_id: str):
        start = time.time()

        result1 = await activity1()
        workflow.logger.info(f"Activity1 took: {time.time() - start:.2f}s")

        start = time.time()
        result2 = await activity2()
        workflow.logger.info(f"Activity2 took: {time.time() - start:.2f}s")
```

---

## Advanced Debugging

### Enable Temporal Worker Debug Logs

```bash
# Edit docker-compose.yml
services:
  worker-rust:
    environment:
      TEMPORAL_LOG_LEVEL: DEBUG
      LOG_LEVEL: DEBUG

# Restart
docker-compose -f docker-compose.yml restart worker-rust
```

### Inspect Temporal Workflows via CLI

```bash
# Install Temporal CLI
docker exec fuzzforge-temporal tctl

# List workflows
docker exec fuzzforge-temporal tctl workflow list

# Describe workflow
docker exec fuzzforge-temporal tctl workflow describe -w security_assessment-abc123

# Show workflow history
docker exec fuzzforge-temporal tctl workflow show -w security_assessment-abc123
```

### Check Network Connectivity

```bash
# From worker to Temporal
docker exec fuzzforge-worker-rust ping temporal

# From worker to MinIO
docker exec fuzzforge-worker-rust curl http://minio:9000

# From host to services
curl http://localhost:8080  # Temporal UI
curl http://localhost:9000  # MinIO
curl http://localhost:8000/health  # Backend
```

---

## Debugging Best Practices

1. **Always check Temporal UI first** - It shows the most complete execution history
2. **Use structured logging** - Include workflow_id, target_id in log messages
3. **Log at decision points** - Before/after each major operation
4. **Keep worker logs** - They persist across workflow runs
5. **Test modules in isolation** - Use `docker exec` to test before integrating
6. **Use debug builds** - Enable DEBUG logging during development
7. **Monitor resources** - Use `docker stats` to catch resource issues

---

## Getting Help

If you're still stuck:

1. **Collect diagnostic info:**
   ```bash
   # Save all logs
   docker-compose -f docker-compose.yml logs > fuzzforge-logs.txt

   # Check service status
   docker-compose -f docker-compose.yml ps > service-status.txt
   ```

2. **Check Temporal UI** and take screenshots of:
   - Workflow execution timeline
   - Failed activity details
   - Error messages

3. **Report issue** with:
   - Workflow name and run_id
   - Error messages from logs
   - Screenshots from Temporal UI
   - Steps to reproduce

---

**Happy debugging!** 🐛🔍
