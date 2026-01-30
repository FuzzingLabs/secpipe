# FuzzForge Benchmark Suite

Performance benchmarking infrastructure organized by module category.

## Directory Structure

```
benchmarks/
├── conftest.py              # Benchmark fixtures
├── category_configs.py      # Category-specific thresholds
├── by_category/             # Benchmarks organized by category
│   ├── fuzzer/
│   │   ├── bench_cargo_fuzz.py
│   │   └── bench_atheris.py
│   ├── scanner/
│   │   └── bench_file_scanner.py
│   ├── secret_detection/
│   │   ├── bench_gitleaks.py
│   │   └── bench_trufflehog.py
│   └── analyzer/
│       └── bench_security_analyzer.py
├── fixtures/                # Benchmark test data
│   ├── small/               # ~1K LOC
│   ├── medium/              # ~10K LOC
│   └── large/               # ~100K LOC
└── results/                 # Benchmark results (JSON)
```

## Module Categories

### Fuzzer
**Expected Metrics**: execs/sec, coverage_rate, time_to_crash, memory_usage

**Performance Thresholds**:
- Min 1000 execs/sec
- Max 10s for small projects
- Max 2GB memory

### Scanner
**Expected Metrics**: files/sec, LOC/sec, findings_count

**Performance Thresholds**:
- Min 100 files/sec
- Min 10K LOC/sec
- Max 512MB memory

### Secret Detection
**Expected Metrics**: patterns/sec, precision, recall, F1

**Performance Thresholds**:
- Min 90% precision
- Min 95% recall
- Max 5 false positives per 100 secrets

### Analyzer
**Expected Metrics**: analysis_depth, files/sec, accuracy

**Performance Thresholds**:
- Min 10 files/sec (deep analysis)
- Min 85% accuracy
- Max 2GB memory

## Running Benchmarks

### All Benchmarks
```bash
cd backend
pytest benchmarks/ --benchmark-only -v
```

### Specific Category
```bash
pytest benchmarks/by_category/fuzzer/ --benchmark-only -v
```

### With Comparison
```bash
# Run and save baseline
pytest benchmarks/ --benchmark-only --benchmark-save=baseline

# Compare against baseline
pytest benchmarks/ --benchmark-only --benchmark-compare=baseline
```

### Generate Histogram
```bash
pytest benchmarks/ --benchmark-only --benchmark-histogram=histogram
```

## Benchmark Results

Results are saved as JSON and include:
- Mean execution time
- Standard deviation
- Min/Max values
- Iterations per second
- Memory usage

Example output:
```
------------------------ benchmark: fuzzer --------------------------
Name                                Mean      StdDev    Ops/Sec
bench_cargo_fuzz[discovery]        0.0012s   0.0001s   833.33
bench_cargo_fuzz[execution]        0.1250s   0.0050s     8.00
bench_cargo_fuzz[memory]           0.0100s   0.0005s   100.00
---------------------------------------------------------------------
```

## CI/CD Integration

Benchmarks run:
- **Nightly**: Full benchmark suite, track trends
- **On PR**: When benchmarks/ or modules/ changed
- **Manual**: Via workflow_dispatch

### Regression Detection

Benchmarks automatically fail if:
- Performance degrades >10%
- Memory usage exceeds thresholds
- Throughput drops below minimum

See `.github/workflows/benchmark.yml` for configuration.

## Adding New Benchmarks

### 1. Create benchmark file in category directory
```python
# benchmarks/by_category/fuzzer/bench_new_fuzzer.py

import pytest
from benchmarks.category_configs import ModuleCategory, get_threshold

@pytest.mark.benchmark(group="fuzzer")
def test_execution_performance(benchmark, new_fuzzer, test_workspace):
    """Benchmark execution speed"""
    result = benchmark(new_fuzzer.execute, config, test_workspace)

    # Validate against threshold
    threshold = get_threshold(ModuleCategory.FUZZER, "max_execution_time_small")
    assert result.execution_time < threshold
```

### 2. Update category_configs.py if needed
Add new thresholds or metrics for your module.

### 3. Run locally
```bash
pytest benchmarks/by_category/fuzzer/bench_new_fuzzer.py --benchmark-only -v
```

## Best Practices

1. **Use mocking** for external dependencies (network, disk I/O)
2. **Fixed iterations** for consistent benchmarking
3. **Warm-up runs** for JIT-compiled code
4. **Category-specific metrics** aligned with module purpose
5. **Realistic fixtures** that represent actual use cases
6. **Memory profiling** using tracemalloc
7. **Compare apples to apples** within the same category

## Interpreting Results

### Good Performance
- ✅ Execution time below threshold
- ✅ Memory usage within limits
- ✅ Throughput meets minimum
- ✅ <5% variance across runs

### Performance Issues
- ⚠️ Execution time 10-20% over threshold
- ❌ Execution time >20% over threshold
- ❌ Memory leaks (increasing over iterations)
- ❌ High variance (>10%) indicates instability

## Tracking Performance Over Time

Benchmark results are stored as artifacts with:
- Commit SHA
- Timestamp
- Environment details (Python version, OS)
- Full metrics

Use these to track long-term performance trends and detect gradual degradation.
