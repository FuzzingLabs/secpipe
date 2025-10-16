# Changelog

All notable changes to FuzzForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2025-01-16

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
- Removed obsolete `volume_mode` references across all documentation
- Added `.env` configuration guide for AI agent API keys
- Fixed worker startup instructions with correct service names
- Updated docker compose commands to modern syntax

#### Worker Management
- Added `worker_service` field to API responses for correct service naming
- Improved error messages with actionable manual start commands
- Fixed default parameters for gitleaks (now uses `no_git=True` by default)

### 🐛 Bug Fixes

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

## [0.6.0] - 2024-12-XX

### Features
- Initial Temporal migration
- Fuzzing workflows (Atheris, Cargo, OSS-Fuzz)
- Security assessment workflow
- Basic CLI commands

---

[0.7.0]: https://github.com/FuzzingLabs/fuzzforge_ai/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/FuzzingLabs/fuzzforge_ai/releases/tag/v0.6.0
