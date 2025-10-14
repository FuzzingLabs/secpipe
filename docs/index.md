# FuzzForge Documentation

Welcome to FuzzForge, a comprehensive security analysis platform built on Temporal that automates security testing workflows. FuzzForge provides production-ready workflows that run static analysis, secret detection, infrastructure scanning, penetration testing, and custom fuzzing campaigns with Docker-based isolation and SARIF-compliant reporting.

## 🚀 Quick Navigation

### 📚 **Tutorials** - *Learn by doing*
Perfect for newcomers who want to learn FuzzForge step by step.

- [**Getting Started**](tutorials/getting-started.md) - Complete setup from installation to first workflow
- [**First Workflow**](tutorials/first-workflow.md) - Run your first security workflow
- [**Building Custom Workflows**](tutorials/building-custom-workflow.md) - Create and deploy custom workflows

### 🛠️ **How-To Guides** - *Problem-focused solutions*
Step-by-step guides for specific tasks and common problems.

- [**Installation**](how-to/installation.md) - Install FuzzForge with proper Docker setup
- [**Docker Setup**](how-to/docker-setup.md) - Configure Docker with insecure registry (required)
- [**Running Workflows**](how-to/running-workflows.md) - Execute different workflow types
- [**CLI Usage**](how-to/cli-usage.md) - Command-line interface patterns
- [**API Integration**](how-to/api-integration.md) - REST API usage and integration
- [**MCP Integration**](how-to/mcp-integration.md) - AI assistant integration setup
- [**Troubleshooting**](how-to/troubleshooting.md) - Common issues and solutions

### 💡 **Concepts** - *Understanding-oriented*
Background information and conceptual explanations.

- [**Architecture**](concepts/architecture.md) - System design and component interactions
- [**Workflows**](concepts/workflows.md) - How workflows function and interact
- [**Security Analysis**](concepts/security-analysis.md) - Security analysis methodology
- [**Docker Containers**](concepts/docker-containers.md) - Containerization approach
- [**SARIF Format**](concepts/sarif-format.md) - Industry-standard security results format

### 📖 **Reference** - *Information-oriented*
Technical reference materials and specifications.

#### Workflows
- [**All Workflows**](reference/workflows/index.md) - Complete workflow reference
- [**Static Analysis**](reference/workflows/static-analysis.md) - Code vulnerability detection
- [**Secret Detection**](reference/workflows/secret-detection.md) - Credential discovery
- [**Infrastructure Scan**](reference/workflows/infrastructure-scan.md) - Infrastructure security
- [**Penetration Testing**](reference/workflows/penetration-testing.md) - Security testing
- [**Language Fuzzing**](reference/workflows/language-fuzzing.md) - Input validation testing
- [**Security Assessment**](reference/workflows/security-assessment.md) - Comprehensive analysis

#### APIs and Interfaces
- [**REST API**](reference/api/index.md) - Complete API documentation
- [**CLI Reference**](reference/cli/index.md) - Command-line interface
- [**Configuration**](reference/configuration.md) - System configuration options

#### Additional Resources
- [**AI Orchestration (Advanced)**](../ai/docs/index.md) - Multi-agent orchestration, A2A services, ingestion, and LLM configuration
- [**Docker Configuration**](reference/docker-configuration.md) - Complete Docker setup requirements
- [**Contributing**](reference/contributing.md) - Development and contribution guidelines
- [**FAQ**](reference/faq.md) - Frequently asked questions
- [**Changelog**](reference/changelog.md) - Version history and updates

---

## 🎯 FuzzForge at a Glance

**6 Production Workflows:**
- Static Analysis (Semgrep, Bandit, CodeQL)
- Secret Detection (TruffleHog, Gitleaks, detect-secrets)
- Infrastructure Scan (Checkov, Hadolint, Kubesec)
- Penetration Testing (Nuclei, Nmap, SQLMap, Nikto)
- Language Fuzzing (AFL++, libFuzzer, Cargo Fuzz)
- Security Assessment (Comprehensive multi-tool analysis)

**Multiple Interfaces:**
- 💻 **CLI**: `fuzzforge runs submit static_analysis_scan /path/to/code`
- 🐍 **Python SDK**: Programmatic workflow integration
- 🌐 **REST API**: HTTP-based workflow management
- 🤖 **MCP**: AI assistant integration (Claude, ChatGPT)

**Key Features:**
- Container-based workflow execution with Docker isolation
- SARIF-compliant security results format
- Real-time workflow monitoring and progress tracking
- Persistent result storage with shared volumes
- Custom Docker image building for specialized tools

---

## 🚨 Important Setup Requirement

**Docker Insecure Registry Configuration Required**

FuzzForge uses a local Docker registry for workflow images. You **must** configure Docker to allow insecure registries:

```json
{
  "insecure-registries": ["localhost:5001"]
}
```

See [Docker Setup Guide](how-to/docker-setup.md) for detailed configuration instructions.

---

## 📋 Documentation Framework

This documentation follows the [Diátaxis framework](https://diataxis.fr/):

- **Tutorials**: Learning-oriented, hands-on lessons
- **How-to guides**: Problem-oriented, step-by-step instructions
- **Concepts**: Understanding-oriented, theoretical knowledge
- **Reference**: Information-oriented, technical specifications

---

**New to FuzzForge?** Start with the [Getting Started Tutorial](tutorials/getting-started.md)

**Need help?** Check the [FAQ](reference/faq.md) or [Troubleshooting Guide](how-to/troubleshooting.md)

**Want to contribute?** See the [Contributing Guide](reference/contributing.md)
