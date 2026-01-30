# Changelog

All notable changes to FuzzForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 📝 Documentation
- Added comprehensive worker startup documentation across all guides
- Added workflow-to-worker mapping tables in README, troubleshooting guide, getting started guide, and docker setup guide
- Fixed broken documentation links in CLI reference
- Added WEEK_SUMMARY*.md pattern to .gitignore

---

## [0.7.3] - 2025-10-30

### 🎯 Major Features

#### Android Static Analysis Workflow
- **Added comprehensive Android security testing workflow** (`android_static_analysis`):
  - Jadx decompiler for APK → Java source code decompilation
  - OpenGrep/Semgrep static analysis with custom Android security rules
  - MobSF integration for comprehensive mobile security scanning
  - SARIF report generation with unified findings format
  - Test results: Successfully decompiled 4,145 Java files, found 8 security vulnerabilities
  - Full workflow completes in ~1.5 minutes

#### Platform-Aware Worker Architecture
- **ARM64 (Apple Silicon) support**:
  - Automatic platform detection (ARM64 vs x86_64) in CLI using `platform.machine()`
  - Worker metadata convention (`metadata.yaml`) for platform-specific capabilities
  - Multi-Dockerfile support: `Dockerfile.amd64` (full toolchain) and `Dockerfile.arm64` (optimized)
  - Conditional module imports for graceful degradation (MobSF skips on ARM64)
  - Backend path resolution via `FUZZFORGE_HOST_ROOT` for CLI worker management
- **Worker selection logic**:
  - CLI automatically selects appropriate Dockerfile based on detected platform
  - Multi-strategy path resolution (API → .fuzzforge marker → environment variable)
  - Platform-specific tool availability documented in metadata

#### Python SAST Workflow
- **Added Python Static Application Security Testing workflow** (`python_sast`):
  - Bandit for Python security linting (SAST)
  - MyPy for static type checking
  - Safety for dependency vulnerability scanning
  - Integrated SARIF reporter for unified findings format
  - Auto-start Python worker on-demand

### ✨ Enhancements

#### CI/CD Improvements
- Added automated worker validation in CI pipeline
- Docker build checks for all workers before merge
- Worker file change detection for selective builds
- Optimized Docker layer caching for faster builds
- Dev branch testing workflow triggers

#### CLI Improvements
- Fixed live monitoring bug in `ff monitor live` command
- Enhanced `ff findings` command with better table formatting
- Improved `ff monitor` with clearer status displays
- Auto-start workers on-demand when workflows require them
- Better error messages with actionable manual start commands

#### Worker Management
- Standardized worker service names (`worker-python`, `worker-android`, etc.)
- Added missing `worker-secrets` to repository
- Improved worker naming consistency across codebase

#### LiteLLM Integration
- Centralized LLM provider management with proxy
- Governance and request/response routing
- OTEL collector integration for observability
- Environment-based configurable timeouts
- Optional `.env.litellm` configuration

### 🐛 Bug Fixes

- Fixed MobSF API key generation from secret file (SHA256 hash)
- Corrected Temporal activity names (decompile_with_jadx, scan_with_opengrep, scan_with_mobsf)
- Resolved linter errors across codebase
- Fixed unused import issues to pass CI checks
- Removed deprecated workflow parameters
- Docker Compose version compatibility fixes

### 🔧 Technical Changes

- Conditional import pattern for optional dependencies (MobSF on ARM64)
- Multi-platform Dockerfile architecture
- Worker metadata convention for capability declaration
- Improved CI worker build optimization
- Enhanced storage activity error handling

### 📝 Test Projects

- Added `test_projects/android_test/` with BeetleBug.apk and shopnest.apk
- Android workflow validation with real APK samples
- ARM64 platform testing and validation

---

## [0.7.2] - 2025-10-22

### 🐛 Bug Fixes
- Fixed worker naming inconsistencies across codebase
- Improved monitor command consolidation and usability
- Enhanced findings CLI with better formatting and display
- Added missing secrets worker to repository

### 📝 Documentation
- Added benchmark results files to git for secret detection workflows

**Note:** v0.7.1 was re-tagged as v0.7.2 (both point to the same commit)

---

## [0.7.0] - 2025-10-16

### 🎯 Major Features

#### Secret Detection Workflows
- **Added three secret detection workflows**:
  - `gitleaks_detection` - Pattern-based secret scanning
  - `trufflehog_detection` - Entropy-based secret detection with verification
  - `llm_secret_detection` - AI-powered semantic secret detection using LLMs
- **Comprehensive benchmarking infrastructure**:
  - 32-secret ground truth dataset for precision/recall testing
  - Difficulty levels: 12 Easy, 10 Medium, 10 Hard secrets
  - SARIF-formatted output for all workflows
  - Achieved 100% recall with LLM-based detection on benchmark dataset

#### AI Module & Agent Integration
- Added A2A (Agent-to-Agent) wrapper for multi-agent orchestration
- Task agent implementation with Google ADK
- LLM analysis workflow for code security analysis
- Reactivated AI agent command (`ff ai agent`)

#### Temporal Migration Complete
- Fully migrated from Prefect to Temporal for workflow orchestration
- MinIO storage for unified file handling (replaces volume mounts)
- Vertical workers with pre-built security toolchains
- Improved worker lifecycle management

#### CI/CD Integration
- Ephemeral deployment model for testing
- Automated workflow validation in CI pipeline

### ✨ Enhancements

#### Documentation
- Updated README for Temporal + MinIO architecture
- Added `.env` configuration guide for AI agent API keys
- Fixed worker startup instructions with correct service names
- Updated docker compose commands to modern syntax

#### Worker Management
- Added `worker_service` field to API responses for correct service naming
- Improved error messages with actionable manual start commands
- Fixed default parameters for gitleaks (now uses `no_git=True` by default)

### 🐛 Bug Fixes

- Fixed default parameters from metadata.yaml not being applied to workflows when no parameters provided
- Fixed gitleaks workflow failing on uploaded directories without Git history
- Fixed worker startup command suggestions (now uses `docker compose up -d` with service names)
- Fixed missing `cognify_text` method in CogneeProjectIntegration

### 🔧 Technical Changes

- Updated all package versions to 0.7.0
- Improved SARIF output formatting for secret detection workflows
- Enhanced benchmark validation with ground truth JSON
- Better integration between CLI and backend for worker management

### 📝 Test Projects

- Added `secret_detection_benchmark` with 32 documented secrets
- Ground truth JSON for automated precision/recall calculations
- Updated `vulnerable_app` for comprehensive security testing

---

## [0.6.0] - Undocumented

### Features
- Initial Temporal migration
- Fuzzing workflows (Atheris, Cargo, OSS-Fuzz)
- Security assessment workflow
- Basic CLI commands

**Note:** No git tag exists for v0.6.0. Release date undocumented.

---

[0.7.3]: https://github.com/FuzzingLabs/fuzzforge_ai/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/FuzzingLabs/fuzzforge_ai/compare/v0.7.0...v0.7.2
[0.7.0]: https://github.com/FuzzingLabs/fuzzforge_ai/releases/tag/v0.7.0
[0.6.0]: https://github.com/FuzzingLabs/fuzzforge_ai/tree/v0.6.0
