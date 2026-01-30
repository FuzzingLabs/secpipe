# Secret Detection Tools Comparison

**Target**: secret_detection_benchmark
**Tools**: Gitleaks, TruffleHog, LLM (gpt-4o-mini), LLM (gpt-5-mini)


## Summary

| Tool | Secrets | Files | Avg/File | Time (s) |
|------|---------|-------|----------|----------|
| Gitleaks | 12 | 10 | 1.2 | 5.18 |
| TruffleHog | 1 | 1 | 1.0 | 5.06 |
| LLM (gpt-4o-mini) | 30 | 15 | 2.0 | 296.85 |
| LLM (gpt-5-mini) | 41 | 16 | 2.6 | 618.55 |

## Agreement Analysis

Secrets found by different numbers of tools:

- **3 tools agree**: 6 secrets
- **2 tools agree**: 22 secrets
- **Only 1 tool found**: 22 secrets

## Tool Agreement Matrix

Number of common secrets found by tool pairs:

| Tool | Gitleaks | TruffleHog | gpt-4o-mini | gpt-5-mini |
|------|------|------|------|------|
| Gitleaks | 12 | 0 | 7 | 11 |
| TruffleHog | 0 | 1 | 0 | 0 |
| gpt-4o-mini | 7 | 0 | 30 | 22 |
| gpt-5-mini | 11 | 0 | 22 | 41 |

## Per-File Detailed Comparison

Secrets found per file by each tool:

| File | Gitleaks | TruffleHog | gpt-4o-mini | gpt-5-mini | Total |
|------|------|------|------|------|------|
| `src/obfuscated.py` | 2 | 0 | 6 | 7 | **15** |
| `src/advanced.js` | 0 | 0 | 5 | 7 | **12** |
| `src/config.py` | 1 | 0 | 0 | 6 | **7** |
| `.env` | 1 | 0 | 2 | 2 | **5** |
| `config/keys.yaml` | 1 | 0 | 2 | 2 | **5** |
| `config/oauth.json` | 1 | 0 | 2 | 2 | **5** |
| `config/settings.py` | 2 | 0 | 0 | 3 | **5** |
| `scripts/deploy.sh` | 1 | 0 | 2 | 2 | **5** |
| `config/legacy.ini` | 0 | 0 | 2 | 2 | **4** |
| `src/Crypto.go` | 0 | 0 | 2 | 2 | **4** |
| `config/app.properties` | 1 | 0 | 1 | 1 | **3** |
| `config/database.yaml` | 0 | 1 | 1 | 1 | **3** |
| `src/Main.java` | 1 | 0 | 1 | 1 | **3** |
| `id_rsa` | 1 | 0 | 1 | 0 | **2** |
| `scripts/webhook.js` | 0 | 0 | 1 | 1 | **2** |
| ... and 2 more files | ... | ... | ... | ... | ... |

## File Type Breakdown

| Type | Gitleaks | TruffleHog | gpt-4o-mini | gpt-5-mini |
|------|------|------|------|------|
| `.env` | 1 files | 0 files | 1 files | 1 files |
| `.go` | 0 files | 0 files | 1 files | 1 files |
| `.ini` | 0 files | 0 files | 1 files | 1 files |
| `.java` | 1 files | 0 files | 1 files | 1 files |
| `.js` | 0 files | 0 files | 2 files | 2 files |
| `.json` | 1 files | 0 files | 1 files | 1 files |
| `.properties` | 1 files | 0 files | 1 files | 1 files |
| `.py` | 3 files | 0 files | 2 files | 4 files |
| `.sh` | 1 files | 0 files | 1 files | 1 files |
| `.sql` | 0 files | 0 files | 1 files | 1 files |
| `.yaml` | 1 files | 1 files | 2 files | 2 files |
| `[no extension]` | 1 files | 0 files | 1 files | 0 files |

## Files Analyzed

**Total unique files with secrets**: 17


### Gitleaks

Found secrets in **10 files**:

- `config/settings.py`: 2 secrets (lines: 6, 9)
- `src/obfuscated.py`: 2 secrets (lines: 7, 17)
- `.env`: 1 secrets (lines: 3)
- `config/app.properties`: 1 secrets (lines: 6)
- `config/keys.yaml`: 1 secrets (lines: 6)
- `id_rsa`: 1 secrets (lines: 1)
- `config/oauth.json`: 1 secrets (lines: 4)
- `scripts/deploy.sh`: 1 secrets (lines: 5)
- `src/Main.java`: 1 secrets (lines: 5)
- `src/config.py`: 1 secrets (lines: 7)

### TruffleHog

Found secrets in **1 files**:

- `config/database.yaml`: 1 secrets (lines: 6)

### LLM (gpt-4o-mini)

Found secrets in **15 files**:

- `src/obfuscated.py`: 6 secrets (lines: 7, 10, 13, 18, 20...)
- `src/advanced.js`: 5 secrets (lines: 4, 7, 10, 12, 17)
- `src/Crypto.go`: 2 secrets (lines: 6, 10)
- `.env`: 2 secrets (lines: 3, 4)
- `config/keys.yaml`: 2 secrets (lines: 6, 12)
- `config/oauth.json`: 2 secrets (lines: 3, 4)
- `config/legacy.ini`: 2 secrets (lines: 4, 7)
- `scripts/deploy.sh`: 2 secrets (lines: 6, 9)
- `src/app.py`: 1 secrets (lines: 7)
- `scripts/webhook.js`: 1 secrets (lines: 4)
- ... and 5 more files

### LLM (gpt-5-mini)

Found secrets in **16 files**:

- `src/obfuscated.py`: 7 secrets (lines: 7, 10, 13, 14, 17...)
- `src/advanced.js`: 7 secrets (lines: 4, 7, 9, 10, 13...)
- `src/config.py`: 6 secrets (lines: 7, 10, 13, 14, 15...)
- `config/settings.py`: 3 secrets (lines: 6, 9, 20)
- `src/Crypto.go`: 2 secrets (lines: 10, 15)
- `.env`: 2 secrets (lines: 3, 4)
- `config/keys.yaml`: 2 secrets (lines: 6, 12)
- `config/oauth.json`: 2 secrets (lines: 3, 4)
- `config/legacy.ini`: 2 secrets (lines: 3, 7)
- `scripts/deploy.sh`: 2 secrets (lines: 5, 10)
- ... and 6 more files

## Overlap Analysis


**No files were found by all tools**


## Ground Truth Analysis

**Expected secrets**: 32 (documented in ground truth)

### Tool Performance vs Ground Truth

| Tool | Found | Expected | Recall | Extra Findings |
|------|-------|----------|--------|----------------|
| Gitleaks | 12 | 32 | 37.5% | 0 |
| TruffleHog | 1 | 32 | 0.0% | 1 |
| LLM (gpt-4o-mini) | 30 | 32 | 56.2% | 12 |
| LLM (gpt-5-mini) | 41 | 32 | 84.4% | 14 |

### LLM Extra Findings Explanation

LLMs may find more than 30 secrets because they detect:

- **Split secret components**: Each part of `DB_PASS_PART1 + PART2 + PART3` counted separately
- **Join operations**: Lines like `''.join(AWS_SECRET_CHARS)` flagged as additional exposure
- **Decoding functions**: Code that reveals secrets (e.g., `base64.b64decode()`, `codecs.decode()`)
- **Comment identifiers**: Lines marking secret locations without plaintext values

These are *technically correct* detections of secret exposure points, not false positives.
The ground truth documents 30 'primary' secrets, but the codebase has additional derivative exposures.


## Performance Summary

- **Most secrets found**: LLM (gpt-5-mini) (41 secrets)
- **Most files covered**: LLM (gpt-5-mini) (16 files)
- **Fastest**: TruffleHog (5.06s)