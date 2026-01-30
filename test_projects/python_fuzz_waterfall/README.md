# Python Fuzzing Test - Waterfall Vulnerability

This project demonstrates a **stateful vulnerability** that Atheris can discover through fuzzing.

## Vulnerability Description

The `check_secret()` function in `main.py` validates input character by character against the secret string "FUZZINGLABS". This creates a **waterfall vulnerability** where:

1. State leaks through the global `progress` variable
2. Each correct character advances the progress counter
3. When all 11 characters are provided in order, the function crashes with `SystemError`

This pattern is analogous to:
- Timing attacks on password checkers
- Protocol state machines with sequential validation
- Multi-step authentication flows

## Files

- `main.py` - Main application with vulnerable `check_secret()` function
- `fuzz_target.py` - Atheris fuzzing harness (contains `TestOneInput()`)
- `README.md` - This file

## How to Fuzz

### Using FuzzForge CLI

```bash
# Initialize FuzzForge in this directory
cd test_projects/python_fuzz_waterfall/
ff init

# Run fuzzing workflow (uploads code to MinIO)
ff workflow run atheris_fuzzing .

# The workflow will:
# 1. Upload this directory to MinIO
# 2. Worker downloads and extracts the code
# 3. Worker discovers fuzz_target.py (has TestOneInput)
# 4. Worker runs Atheris fuzzing
# 5. Reports real-time stats every 5 seconds
# 6. Finds crash when "FUZZINGLABS" is discovered
```

### Using FuzzForge SDK

```python
from fuzzforge_sdk import FuzzForgeClient
from pathlib import Path

client = FuzzForgeClient(base_url="http://localhost:8000")

# Upload and run fuzzing
response = client.submit_workflow_with_upload(
    workflow_name="atheris_fuzzing",
    target_path=Path("./"),
    parameters={
        "max_iterations": 100000,
        "timeout_seconds": 300
    }
)

print(f"Workflow started: {response.run_id}")

# Wait for completion
final_status = client.wait_for_completion(response.run_id)
findings = client.get_run_findings(response.run_id)

for finding in findings:
    print(f"Crash: {finding.title}")
    print(f"Input: {finding.metadata.get('crash_input_hex')}")
```

### Standalone (Without FuzzForge)

```bash
# Install Atheris
pip install atheris

# Run fuzzing directly
python fuzz_target.py
```

## Expected Behavior

When fuzzing:

1. **Initial phase**: Random exploration, progress = 0
2. **Discovery phase**: Atheris finds 'F' (first char), progress = 1
3. **Incremental progress**: Finds 'U', then 'Z', etc.
4. **Crash**: When full "FUZZINGLABS" discovered, crashes with:
   ```
   SystemError: SECRET COMPROMISED: FUZZINGLABS
   ```

## Monitoring

Watch real-time fuzzing stats:

```bash
docker logs fuzzforge-worker-python -f | grep LIVE_STATS
```

Output example:
```
INFO - LIVE_STATS - executions=1523 execs_per_sec=1523.0 crashes=0
INFO - LIVE_STATS - executions=7842 execs_per_sec=2104.2 crashes=0
INFO - LIVE_STATS - executions=15234 execs_per_sec=2167.0 crashes=1  ← Crash found!
```

## Vulnerability Details

**CVE**: N/A (demonstration vulnerability)
**CWE**: CWE-208 (Observable Timing Discrepancy)
**Severity**: Critical (in real systems)

**Fix**: Remove state-based checking or implement constant-time comparison:

```python
def check_secret_safe(input_data: bytes) -> bool:
    """Constant-time comparison"""
    import hmac
    return hmac.compare_digest(input_data, SECRET.encode())
```

## Adjusting Difficulty

If fuzzing finds the crash too quickly, extend the secret:

```python
# In main.py, change:
SECRET = "FUZZINGLABSSECURITYTESTING"  # 26 characters instead of 11
```

## License

MIT License - This is a demonstration project for educational purposes.
