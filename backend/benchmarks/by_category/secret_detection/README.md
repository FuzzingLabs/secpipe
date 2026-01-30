# Secret Detection Benchmarks

Comprehensive benchmarking suite comparing secret detection tools via complete workflow execution:
- **Gitleaks** - Fast pattern-based detection
- **TruffleHog** - Entropy analysis with verification
- **LLM Detector** - AI-powered semantic analysis (gpt-4o-mini, gpt-5-mini)

## Quick Start

### Run All Comparisons

```bash
cd backend
python benchmarks/by_category/secret_detection/compare_tools.py
```

This will run all workflows on `test_projects/secret_detection_benchmark/` and generate comparison reports.

### Run Benchmark Tests

```bash
# All benchmarks (Gitleaks, TruffleHog, LLM with 3 models)
pytest benchmarks/by_category/secret_detection/bench_comparison.py --benchmark-only -v

# Specific tool only
pytest benchmarks/by_category/secret_detection/bench_comparison.py::TestSecretDetectionComparison::test_gitleaks_workflow --benchmark-only -v

# Performance tests only
pytest benchmarks/by_category/secret_detection/bench_comparison.py::TestSecretDetectionPerformance --benchmark-only -v
```

## Ground Truth Dataset

**Controlled Benchmark** (`test_projects/secret_detection_benchmark/`)

**Exactly 32 documented secrets** for accurate precision/recall testing:
- **12 Easy**: Standard patterns (AWS keys, GitHub PATs, Stripe keys, SSH keys)
- **10 Medium**: Obfuscated (Base64, hex, concatenated, in comments, Unicode)
- **10 Hard**: Well hidden (ROT13, binary, XOR, reversed, template strings, regex patterns)

All secrets documented in `secret_detection_benchmark_GROUND_TRUTH.json` with exact file paths and line numbers.

See `test_projects/secret_detection_benchmark/README.md` for details.

## Metrics Measured

### Accuracy Metrics
- **Precision**: TP / (TP + FP) - How many detected secrets are real?
- **Recall**: TP / (TP + FN) - How many real secrets were found?
- **F1 Score**: Harmonic mean of precision and recall
- **False Positive Rate**: FP / Total Detected

### Performance Metrics
- **Execution Time**: Total time to scan all files
- **Throughput**: Files/secrets scanned per second
- **Memory Usage**: Peak memory during execution

### Thresholds (from `category_configs.py`)
- Minimum Precision: 90%
- Minimum Recall: 95%
- Max Execution Time (small): 2.0s
- Max False Positives: 5 per 100 secrets

## Tool Comparison

### Gitleaks
**Strengths:**
- Fastest execution
- Git-aware (commit history scanning)
- Low false positive rate
- No API required
- Works offline

**Weaknesses:**
- Pattern-based only
- May miss obfuscated secrets
- Limited to known patterns

### TruffleHog
**Strengths:**
- Secret verification (validates if active)
- High detection rate with entropy analysis
- Multiple detectors (600+ secret types)
- Catches high-entropy strings

**Weaknesses:**
- Slower than Gitleaks
- Higher false positive rate
- Verification requires network calls

### LLM Detector
**Strengths:**
- Semantic understanding of context
- Catches novel/custom secret patterns
- Can reason about what "looks like" a secret
- Multiple model options (GPT-4, Claude, etc.)
- Understands code context

**Weaknesses:**
- Slowest (API latency + LLM processing)
- Most expensive (LLM API costs)
- Requires A2A agent infrastructure
- Accuracy varies by model
- May miss well-disguised secrets

## Results Directory

After running comparisons, results are saved to:
```
benchmarks/by_category/secret_detection/results/
├── comparison_report.md    # Human-readable comparison with:
│                           # - Summary table with secrets/files/avg per file/time
│                           # - Agreement analysis (secrets found by N tools)
│                           # - Tool agreement matrix (overlap between pairs)
│                           # - Per-file detailed comparison table
│                           # - File type breakdown
│                           # - Files analyzed by each tool
│                           # - Overlap analysis and performance summary
└── comparison_results.json # Machine-readable data with findings_by_file
```

## Latest Benchmark Results

Run the benchmark to generate results:
```bash
cd backend
python benchmarks/by_category/secret_detection/compare_tools.py
```

Results are saved to `results/comparison_report.md` with:
- Summary table (secrets found, files scanned, time)
- Agreement analysis (how many tools found each secret)
- Tool agreement matrix (overlap between tools)
- Per-file detailed comparison
- File type breakdown

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/benchmark-secrets.yml
name: Secret Detection Benchmark

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest-benchmark

      - name: Run benchmarks
        env:
          GITGUARDIAN_API_KEY: ${{ secrets.GITGUARDIAN_API_KEY }}
        run: |
          cd backend
          pytest benchmarks/by_category/secret_detection/bench_comparison.py \
            --benchmark-only \
            --benchmark-json=results.json \
            --gitguardian-api-key

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: backend/results.json
```

## Adding New Tools

To benchmark a new secret detection tool:

1. Create module in `toolbox/modules/secret_detection/`
2. Register in `__init__.py`
3. Add to `compare_tools.py` in `run_all_tools()`
4. Add test in `bench_comparison.py`

## Interpreting Results

### High Precision, Low Recall
Tool is conservative - few false positives but misses secrets.
**Use case**: Production environments where false positives are costly.

### Low Precision, High Recall
Tool is aggressive - finds most secrets but many false positives.
**Use case**: Initial scans where manual review is acceptable.

### Balanced (High F1)
Tool has good balance of precision and recall.
**Use case**: General purpose scanning.

### Fast Execution
Suitable for CI/CD pipelines and pre-commit hooks.

### Slow but Accurate
Better for comprehensive security audits.

## Best Practices

1. **Use multiple tools**: Each has strengths/weaknesses
2. **Combine results**: Union of all findings for maximum coverage
3. **Filter intelligently**: Remove known false positives
4. **Verify findings**: Check if secrets are actually valid
5. **Track over time**: Monitor precision/recall trends
6. **Update regularly**: Patterns evolve, tools improve

## Troubleshooting

### GitGuardian Tests Skipped
- Set `GITGUARDIAN_API_KEY` environment variable
- Use `--gitguardian-api-key` flag

### LLM Tests Skipped
- Ensure A2A agent is running
- Check agent URL in config
- Use `--llm-enabled` flag

### Low Recall
- Check if ground truth is up to date
- Verify tool is configured correctly
- Review missed secrets manually

### High False Positives
- Adjust tool sensitivity
- Add exclusion patterns
- Review false positive list
