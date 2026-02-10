# Harness Tester Feedback Types

Complete reference of all feedback the `harness-tester` module provides to help AI agents improve fuzz harnesses.

## Overview

The harness-tester evaluates harnesses across **6 dimensions** and provides specific, actionable suggestions for each issue detected.

---

## 1. Compilation Feedback

### ✅ Success Cases
- **Compiles successfully** → Strength noted

### ❌ Error Cases

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `undefined_variable` | CRITICAL | "cannot find" in error | Check variable names match function signature. Use exact names from fuzzable_functions.json |
| `type_mismatch` | CRITICAL | "mismatched types" in error | Check function expects types you're passing. Convert fuzzer input to correct type (e.g., &[u8] to &str with from_utf8) |
| `trait_not_implemented` | CRITICAL | "trait" + "not implemented" | Ensure you're using correct types. Some functions require specific trait implementations |
| `compilation_error` | CRITICAL | Any other error | Review error message and fix syntax/type issues. Check function signatures in source code |

### ⚠️ Warning Cases

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `unused_variable` | INFO | "unused" in warning | Remove unused variables or use underscore prefix (_variable) to suppress warning |

---

## 2. Execution Feedback

### ✅ Success Cases
- **Executes without crashing** → Strength noted

### ❌ Error Cases

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `stack_overflow` | CRITICAL | "stack overflow" in crash | Check for infinite recursion or large stack allocations. Use heap allocation (Box, Vec) for large data structures |
| `panic_on_start` | CRITICAL | "panic" in crash | Check initialization code. Ensure required resources are available and input validation doesn't panic on empty input |
| `immediate_crash` | CRITICAL | Crashes on first run | Debug harness initialization. Add error handling and check for null/invalid pointers |
| `infinite_loop` | CRITICAL | Execution timeout | Check for loops that depend on fuzzer input. Add iteration limits or timeout mechanisms |

---

## 3. Coverage Feedback

### ✅ Success Cases
- **>50% coverage** → "Excellent coverage"
- **Good growth** → "Harness exploring code paths"

### ❌ Error Cases

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `no_coverage` | CRITICAL | 0 new edges found | Ensure you're actually calling the target function with fuzzer-provided data. Check that 'data' parameter is passed to function |
| `very_low_coverage` | WARNING | <5% coverage or "none" growth | Harness may not be reaching target code. Verify correct entry point function. Check if input validation rejects all fuzzer data |
| `low_coverage` | WARNING | <20% coverage or "poor" growth | Try fuzzing multiple entry points or remove restrictive input validation. Consider using dictionary for structured inputs |
| `early_stagnation` | INFO | Coverage stops growing <10s | Harness may be hitting input validation barriers. Consider fuzzing with seed corpus of valid inputs |

---

## 4. Performance Feedback

### ✅ Success Cases
- **>1000 execs/s** → "Excellent performance"
- **>500 execs/s** → "Good performance"

### ❌ Error Cases

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `extremely_slow` | CRITICAL | <10 execs/s | Remove file I/O, network operations, or expensive computations from harness loop. Move setup code outside fuzz target function |
| `slow_execution` | WARNING | <100 execs/s | Optimize harness: avoid allocations in hot path, reuse buffers, remove logging. Profile to find bottlenecks |

---

## 5. Stability Feedback

### ✅ Success Cases
- **Stable execution** → Strength noted
- **Found unique crashes** → "Found N potential bugs!"

### ⚠️ Warning Cases

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `unstable_frequent_crashes` | WARNING | >10 crashes per 1000 execs | This might be expected if testing buggy code. If not, add error handling for edge cases or invalid inputs |
| `hangs_detected` | WARNING | Hangs found during trial | Add timeouts to prevent infinite loops. Check for blocking operations or resource exhaustion |

---

## 6. Code Quality Feedback

### Informational

| Issue Type | Severity | Detection | Suggestion |
|------------|----------|-----------|------------|
| `unused_variable` | INFO | Compiler warnings | Clean up code for better maintainability |

---

## Quality Scoring Formula

```
Base Score: 20 points (for compiling + running)

+ Coverage (0-40 points):
  - Excellent growth: +40
  - Good growth: +30
  - Poor growth: +10
  - No growth: +0

+ Performance (0-25 points):
  - >1000 execs/s: +25
  - >500 execs/s: +20
  - >100 execs/s: +10
  - >10 execs/s: +5
  - <10 execs/s: +0

+ Stability (0-15 points):
  - Stable: +15
  - Unstable: +10
  - Crashes frequently: +5

Maximum: 100 points
```

### Verdicts

- **70-100**: `production-ready` → Use for long-term fuzzing campaigns
- **30-69**: `needs-improvement` → Fix issues before production use
- **0-29**: `broken` → Critical issues block execution

---

## Example Feedback Flow

### Scenario 1: Broken Harness (Type Mismatch)

```json
{
  "quality": {
    "score": 0,
    "verdict": "broken",
    "issues": [
      {
        "category": "compilation",
        "severity": "critical",
        "type": "type_mismatch",
        "message": "Type mismatch: expected &[u8], found &str",
        "suggestion": "Check function expects types you're passing. Convert fuzzer input to correct type (e.g., &[u8] to &str with from_utf8)"
      }
    ],
    "recommended_actions": [
      "Fix 1 critical issue(s) preventing execution"
    ]
  }
}
```

**AI Agent Action**: Regenerate harness with correct type conversion

---

### Scenario 2: Low Coverage Harness

```json
{
  "quality": {
    "score": 35,
    "verdict": "needs-improvement",
    "issues": [
      {
        "category": "coverage",
        "severity": "warning",
        "type": "low_coverage",
        "message": "Low coverage: 12% - not exploring enough code paths",
        "suggestion": "Try fuzzing multiple entry points or remove restrictive input validation"
      },
      {
        "category": "performance",
        "severity": "warning",
        "type": "slow_execution",
        "message": "Slow execution: 45 execs/sec (expected 500+)",
        "suggestion": "Optimize harness: avoid allocations in hot path, reuse buffers"
      }
    ],
    "strengths": [
      "Compiles successfully",
      "Executes without crashing"
    ],
    "recommended_actions": [
      "Address 2 warning(s) to improve harness quality"
    ]
  }
}
```

**AI Agent Action**: Remove input validation, optimize performance

---

### Scenario 3: Production-Ready Harness

```json
{
  "quality": {
    "score": 85,
    "verdict": "production-ready",
    "issues": [],
    "strengths": [
      "Compiles successfully",
      "Executes without crashing",
      "Excellent coverage: 67% of target code reached",
      "Excellent performance: 1507 execs/sec",
      "Stable execution - no crashes or hangs"
    ],
    "recommended_actions": [
      "Harness is ready for production fuzzing"
    ]
  }
}
```

**AI Agent Action**: Proceed to long-term fuzzing with cargo-fuzzer

---

## Integration with AI Workflow

```python
def iterative_harness_generation(target_function):
    """AI agent iteratively improves harness based on feedback."""
    
    max_iterations = 3
    
    for iteration in range(max_iterations):
        # Generate or improve harness
        if iteration == 0:
            harness = ai_generate_harness(target_function)
        else:
            harness = ai_improve_harness(previous_harness, feedback)
        
        # Test harness
        result = execute_module("harness-tester", harness)
        evaluation = result["harnesses"][0]
        
        # Check verdict
        if evaluation["quality"]["verdict"] == "production-ready":
            return harness  # Success!
        
        # Extract feedback for next iteration
        feedback = {
            "issues": evaluation["quality"]["issues"],
            "suggestions": [issue["suggestion"] for issue in evaluation["quality"]["issues"]],
            "score": evaluation["quality"]["score"],
            "coverage": evaluation["fuzzing_trial"]["coverage"] if "fuzzing_trial" in evaluation else None,
            "performance": evaluation["fuzzing_trial"]["performance"] if "fuzzing_trial" in evaluation else None
        }
        
        # Store for next iteration
        previous_harness = harness
    
    return harness  # Return best attempt after max iterations
```

---

## Summary

The harness-tester provides **comprehensive, actionable feedback** across 6 dimensions:

1. ✅ **Compilation** - Syntax and type correctness
2. ✅ **Execution** - Runtime stability  
3. ✅ **Coverage** - Code exploration effectiveness
4. ✅ **Performance** - Execution speed
5. ✅ **Stability** - Crash/hang frequency
6. ✅ **Code Quality** - Best practices

Each issue includes:
- **Clear detection** of what went wrong
- **Specific suggestion** on how to fix it
- **Severity level** to prioritize fixes

This enables AI agents to rapidly iterate and produce high-quality fuzz harnesses with minimal human intervention.
