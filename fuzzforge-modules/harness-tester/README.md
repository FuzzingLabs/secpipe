# Harness Tester Module

Tests and evaluates fuzz harnesses with comprehensive feedback for AI-driven iteration.

## Overview

The `harness-tester` module runs a battery of tests on fuzz harnesses to provide actionable feedback:

1. **Compilation Testing** - Validates harness compiles correctly
2. **Execution Testing** - Ensures harness runs without immediate crashes
3. **Fuzzing Trial** - Runs short fuzzing session (default: 30s) to measure:
   - Coverage growth
   - Execution performance (execs/sec)
   - Stability (crashes, hangs)
4. **Quality Assessment** - Generates scored evaluation with specific issues and suggestions

## Feedback Categories

### 1. Compilation Feedback
- Undefined variables → "Check variable names match function signature"
- Type mismatches → "Convert fuzzer input to correct type"
- Missing traits → "Ensure you're using correct types"

### 2. Execution Feedback  
- Stack overflow → "Check for infinite recursion, use heap allocation"
- Immediate panic → "Check initialization code and input validation"
- Timeout/infinite loop → "Add iteration limits"

### 3. Coverage Feedback
- No coverage → "Harness may not be using fuzzer input"
- Very low coverage (<5%) → "May not be reaching target code, check entry point"
- Low coverage (<20%) → "Try fuzzing multiple entry points"
- Good/Excellent coverage → "Harness is exploring code paths well"

### 4. Performance Feedback
- Extremely slow (<10 execs/s) → "Remove file I/O or network operations"
- Slow (<100 execs/s) → "Optimize harness, avoid allocations in hot path"
- Good (>500 execs/s) → Ready for production
- Excellent (>1000 execs/s) → Optimal performance

### 5. Stability Feedback
- Frequent crashes → "Add error handling for edge cases"
- Hangs detected → "Add timeouts to prevent infinite loops"
- Stable → Ready for production

## Usage

```python
# Via MCP
result = execute_module("harness-tester",
    assets_path="/path/to/rust/project",
    configuration={
        "trial_duration_sec": 30,
        "execution_timeout_sec": 10
    })
```

## Input Requirements

- Rust project with `Cargo.toml`
- Fuzz harnesses in `fuzz/fuzz_targets/`
- Source code to analyze

## Output Artifacts

### `harness-evaluation.json`
Complete structured evaluation with:
```json
{
  "harnesses": [
    {
      "name": "fuzz_png_decode",
      "compilation": { "success": true, "time_ms": 4523 },
      "execution": { "success": true },
      "fuzzing_trial": {
        "coverage": {
          "final_edges": 891,
          "growth_rate": "good",
          "percentage_estimate": 67.0
        },
        "performance": {
          "execs_per_sec": 1507.0,
          "performance_rating": "excellent"
        },
        "stability": { "status": "stable" }
      },
      "quality": {
        "score": 85,
        "verdict": "production-ready",
        "issues": [],
        "strengths": ["Excellent performance", "Good coverage"],
        "recommended_actions": ["Ready for production fuzzing"]
      }
    }
  ],
  "summary": {
    "total_harnesses": 1,
    "production_ready": 1,
    "average_score": 85.0
  }
}
```

### `feedback-summary.md`
Human-readable summary with all issues and suggestions.

## Quality Scoring

Harnesses are scored 0-100 based on:

- **Compilation** (20 points): Must compile to proceed
- **Execution** (20 points): Must run without crashing
- **Coverage** (40 points):
  - Excellent growth: 40 pts
  - Good growth: 30 pts  
  - Poor growth: 10 pts
- **Performance** (25 points):
  - >1000 execs/s: 25 pts
  - >500 execs/s: 20 pts
  - >100 execs/s: 10 pts
- **Stability** (15 points):
  - Stable: 15 pts
  - Unstable: 10 pts
  - Crashes frequently: 5 pts

**Verdicts:**
- 70-100: `production-ready`
- 30-69: `needs-improvement`
- 0-29: `broken`

## AI Agent Iteration Pattern

```
1. AI generates harness
2. harness-tester evaluates it
3. Returns: score=35, verdict="needs-improvement"
   Issues: "Low coverage (8%), slow execution (7.8 execs/s)"
   Suggestions: "Check entry point function, remove I/O operations"
4. AI fixes harness based on feedback
5. harness-tester re-evaluates
6. Returns: score=85, verdict="production-ready"
7. Proceed to production fuzzing
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `trial_duration_sec` | 30 | How long to run fuzzing trial |
| `execution_timeout_sec` | 10 | Timeout for execution test |

## See Also

- [Module SDK Documentation](../fuzzforge-modules-sdk/README.md)
- [MODULE_METADATA.md](../MODULE_METADATA.md)
