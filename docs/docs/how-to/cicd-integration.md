# CI/CD Integration Guide

This guide shows you how to integrate FuzzForge into your CI/CD pipeline for automated security testing on every commit, pull request, or scheduled run.

---

## Overview

FuzzForge can run entirely inside CI containers (GitHub Actions, GitLab CI, etc.) with no external infrastructure required. The complete FuzzForge stack—Temporal, PostgreSQL, MinIO, Backend, and workers—starts automatically when needed and cleans up after execution.

### Key Benefits

✅ **Zero Infrastructure**: No servers to maintain
✅ **Ephemeral**: Fresh environment per run
✅ **Resource Efficient**: On-demand workers (v0.7.0) save ~6-7GB RAM
✅ **Fast Feedback**: Fail builds on critical/high findings
✅ **Standards Compliant**: SARIF export for GitHub Security / GitLab SAST

---

## Prerequisites

### Required
- **CI Runner**: Ubuntu with Docker support
- **RAM**: At least 4GB available (7GB on GitHub Actions)
- **Startup Time**: ~60-90 seconds

### Optional
- **jq**: For merging Docker daemon config (auto-installed in examples)
- **Python 3.11+**: For FuzzForge CLI

---

## Quick Start

### 1. Add Startup Scripts

FuzzForge provides helper scripts to configure Docker and start services:

```bash
# Start FuzzForge (configure Docker, start services, wait for health)
bash scripts/ci-start.sh

# Stop and cleanup after execution
bash scripts/ci-stop.sh
```

### 2. Install CLI

```bash
pip install ./cli
```

### 3. Initialize Project

```bash
ff init --api-url http://localhost:8000 --name "CI Security Scan"
```

### 4. Run Workflow

```bash
# Run and fail on error findings
ff workflow run security_assessment . \
  --wait \
  --fail-on error \
  --export-sarif results.sarif
```

---

## Deployment Models

FuzzForge supports two CI/CD deployment models:

### Option A: Ephemeral (Recommended)

**Everything runs inside the CI container for each job.**

```
┌────────────────────────────────────┐
│ GitHub Actions Runner              │
│                                    │
│  ┌──────────────────────────────┐ │
│  │ FuzzForge Stack              │ │
│  │ • Temporal                   │ │
│  │ • PostgreSQL                 │ │
│  │ • MinIO                      │ │
│  │ • Backend                    │ │
│  │ • Workers (on-demand)        │ │
│  └──────────────────────────────┘ │
│                                    │
│  ff workflow run ...               │
└────────────────────────────────────┘
```

**Pros:**
- No infrastructure to maintain
- Complete isolation per run
- Works on GitHub/GitLab free tier

**Cons:**
- 60-90s startup time per run
- Limited to runner resources

**Best For:** Open source projects, infrequent scans, PR checks

### Option B: Persistent Backend

**Backend runs on a separate server, CLI connects remotely.**

```
┌──────────────┐         ┌──────────────────┐
│ CI Runner    │────────▶│ FuzzForge Server │
│ (ff CLI)     │  HTTPS  │ (self-hosted)    │
└──────────────┘         └──────────────────┘
```

**Pros:**
- No startup time
- More resources
- Faster execution

**Cons:**
- Requires infrastructure
- Needs API tokens

**Best For:** Large teams, frequent scans, long fuzzing campaigns

---

## GitHub Actions Integration

### Complete Example

See `.github/workflows/examples/security-scan.yml` for a full working example.

**Basic workflow:**

```yaml
name: Security Scan

on: [pull_request, push]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start FuzzForge
        run: bash scripts/ci-start.sh

      - name: Install CLI
        run: pip install ./cli

      - name: Security Scan
        run: |
          ff init --api-url http://localhost:8000
          ff workflow run security_assessment . \
            --wait \
            --fail-on error \
            --export-sarif results.sarif

      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif

      - name: Cleanup
        if: always()
        run: bash scripts/ci-stop.sh
```

### GitHub Security Tab Integration

Upload SARIF results to see findings directly in GitHub:

```yaml
- name: Upload SARIF to GitHub Security
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

Findings appear in:
- **Security** tab → **Code scanning alerts**
- Pull request annotations
- Commit status checks

---

## GitLab CI Integration

### Complete Example

See `.gitlab-ci.example.yml` for a full working example.

**Basic pipeline:**

```yaml
stages:
  - security

variables:
  FUZZFORGE_API_URL: "http://localhost:8000"

security:scan:
  image: docker:24
  services:
    - docker:24-dind
  before_script:
    - apk add bash python3 py3-pip
    - bash scripts/ci-start.sh
    - pip3 install ./cli --break-system-packages
    - ff init --api-url $FUZZFORGE_API_URL
  script:
    - ff workflow run security_assessment . --wait --fail-on error --export-sarif results.sarif
  artifacts:
    reports:
      sast: results.sarif
  after_script:
    - bash scripts/ci-stop.sh
```

### GitLab SAST Dashboard Integration

The `reports: sast:` section automatically integrates with GitLab's Security Dashboard.

---

## CLI Flags for CI/CD

### `--fail-on`

Fail the build if findings match specified SARIF severity levels.

**Syntax:**
```bash
--fail-on error,warning,note,info,all,none
```

**SARIF Levels:**
- `error` - Critical security issues (fail build)
- `warning` - Potential security issues (may fail build)
- `note` - Informational findings (typically don't fail)
- `info` - Additional context (rarely blocks)
- `all` - Any finding (strictest)
- `none` - Never fail (report only)

**Examples:**
```bash
# Fail on errors only (recommended for CI)
--fail-on error

# Fail on errors or warnings
--fail-on error,warning

# Fail on any finding (strictest)
--fail-on all

# Never fail, just report (useful for monitoring)
--fail-on none
```

**Common Patterns:**
- **PR checks**: `--fail-on error` (block critical issues)
- **Release gates**: `--fail-on error,warning` (stricter)
- **Nightly scans**: `--fail-on none` (monitoring only)
- **Security audit**: `--fail-on all` (maximum strictness)

**Exit Codes:**
- `0` - No blocking findings
- `1` - Found blocking findings or error

### `--export-sarif`

Export SARIF results to a file after workflow completion.

**Syntax:**
```bash
--export-sarif <path>
```

**Example:**
```bash
ff workflow run security_assessment . \
  --wait \
  --export-sarif results.sarif
```

### `--wait`

Wait for workflow execution to complete (required for CI/CD).

**Example:**
```bash
ff workflow run security_assessment . --wait
```

Without `--wait`, the command returns immediately and the workflow runs in the background.

---

## Common Workflows

### PR Security Gate

Block PRs with critical/high findings:

```yaml
on: pull_request

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash scripts/ci-start.sh
      - run: pip install ./cli
      - run: |
          ff init --api-url http://localhost:8000
          ff workflow run security_assessment . --wait --fail-on error
      - if: always()
        run: bash scripts/ci-stop.sh
```

### Secret Detection (Zero Tolerance)

Fail on ANY exposed secrets:

```bash
ff workflow run secret_detection . --wait --fail-on all
```

### Nightly Fuzzing (Report Only)

Run long fuzzing campaigns without failing the build:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily

jobs:
  fuzzing:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - run: bash scripts/ci-start.sh
      - run: pip install ./cli
      - run: |
          ff init --api-url http://localhost:8000
          ff workflow run atheris_fuzzing . \
            max_iterations=100000000 \
            timeout_seconds=7200 \
            --wait \
            --export-sarif fuzzing-results.sarif
        continue-on-error: true
      - if: always()
        run: bash scripts/ci-stop.sh
```

### Release Gate

Block releases with ANY security findings:

```yaml
on:
  push:
    tags:
      - 'v*'

jobs:
  release-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash scripts/ci-start.sh
      - run: pip install ./cli
      - run: |
          ff init --api-url http://localhost:8000
          ff workflow run security_assessment . --wait --fail-on all
```

---

## Performance Optimization

### Startup Time

**Current:** ~60-90 seconds
**Breakdown:**
- Docker daemon restart: 10-15s
- docker-compose up: 30-40s
- Health check wait: 20-30s

**Tips to reduce:**
1. Use `docker-compose.ci.yml` (optional, see below)
2. Cache Docker layers (GitHub Actions)
3. Use self-hosted runners (persistent Docker)

### Optional: CI-Optimized Compose File

Create `docker-compose.ci.yml`:

```yaml
version: '3.8'

services:
  postgresql:
    # Use in-memory storage (faster, ephemeral)
    tmpfs:
      - /var/lib/postgresql/data
    command: postgres -c fsync=off -c full_page_writes=off

  minio:
    # Use in-memory storage
    tmpfs:
      - /data

  temporal:
    healthcheck:
      # More frequent health checks
      interval: 5s
      retries: 10
```

**Usage:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

---

## Troubleshooting

### "Permission denied" connecting to Docker socket

**Solution:** Add user to docker group or use `sudo`.

```bash
# GitHub Actions (already has permissions)
# GitLab CI: use docker:dind service
```

### "Connection refused to localhost:8000"

**Problem:** Services not healthy yet.

**Solution:** Increase health check timeout in `ci-start.sh`:

```bash
timeout 180 bash -c 'until curl -sf http://localhost:8000/health; do sleep 3; done'
```

### "Out of disk space"

**Problem:** Docker volumes filling up.

**Solution:** Cleanup in `after_script`:

```bash
after_script:
  - bash scripts/ci-stop.sh
  - docker system prune -af --volumes
```

### Worker not starting

**Problem:** Worker container exists but not running.

**Solution:** Workers are pre-built but start on-demand (v0.7.0). If a workflow fails immediately, check:

```bash
docker logs fuzzforge-worker-<vertical>
```

---

## Best Practices

1. **Always use `--wait`** in CI/CD pipelines
2. **Set appropriate `--fail-on` levels** for your use case:
   - PR checks: `error` (block critical issues)
   - Release gates: `error,warning` (stricter)
   - Nightly scans: Don't use (report only)
3. **Export SARIF** to integrate with security dashboards
4. **Set timeouts** on CI jobs to prevent hanging
5. **Use artifacts** to preserve findings for review
6. **Cleanup always** with `if: always()` or `after_script`

---

## Advanced: Persistent Backend Setup

For high-frequency usage, deploy FuzzForge on a dedicated server:

### 1. Deploy FuzzForge Server

```bash
# On your CI server
git clone https://github.com/FuzzingLabs/fuzzforge_ai.git
cd fuzzforge_ai
docker-compose up -d
```

### 2. Generate API Token (Future Feature)

```bash
# This will be available in a future release
docker exec fuzzforge-backend python -c "
from src.auth import generate_token
print(generate_token(name='github-actions'))
"
```

### 3. Configure CI to Use Remote Backend

```yaml
env:
  FUZZFORGE_API_URL: https://fuzzforge.company.com
  FUZZFORGE_API_TOKEN: ${{ secrets.FUZZFORGE_TOKEN }}

steps:
  - run: pip install fuzzforge-cli
  - run: ff workflow run security_assessment . --wait --fail-on error
```

**Note:** Authentication is not yet implemented (v0.7.0). Use network isolation or VPN for now.

---

## Examples

- **GitHub Actions**: `.github/workflows/examples/security-scan.yml`
- **GitLab CI**: `.gitlab-ci.example.yml`
- **Startup Script**: `scripts/ci-start.sh`
- **Cleanup Script**: `scripts/ci-stop.sh`

---

## Support

- **Documentation**: [https://docs.fuzzforge.ai](https://docs.fuzzforge.ai)
- **Issues**: [GitHub Issues](https://github.com/FuzzingLabs/fuzzforge_ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/FuzzingLabs/fuzzforge_ai/discussions)
