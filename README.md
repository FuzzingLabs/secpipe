<p align="center">
  <img src="docs/static/img/fuzzforge_banner_github.png" alt="FuzzForge Banner" width="100%">
</p>
<h1 align="center">🚧 FuzzForge is under active development</h1>

<p align="center"><strong>AI-powered workflow automation and AI Agents for AppSec, Fuzzing & Offensive Security</strong></p>

<p align="center">
  <a href="https://discord.com/invite/acqv9FVG"><img src="https://img.shields.io/discord/1420767905255133267?logo=discord&label=Discord" alt="Discord"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL%20%2B%20Apache-orange" alt="License: BSL + Apache"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"/></a>
  <a href="https://fuzzforge.ai"><img src="https://img.shields.io/badge/Website-fuzzforge.ai-blue" alt="Website"/></a>
  <img src="https://img.shields.io/badge/version-0.7.0-green" alt="Version">
  <a href="https://github.com/FuzzingLabs/fuzzforge_ai/stargazers"><img src="https://img.shields.io/github/stars/FuzzingLabs/fuzzforge_ai?style=social" alt="GitHub Stars"></a>
  
</p>

<p align="center">
  <sub>
    <a href="#-overview"><b>Overview</b></a>
    • <a href="#-key-features"><b>Features</b></a>
    • <a href="#-installation"><b>Installation</b></a>
    • <a href="#-quickstart"><b>Quickstart</b></a>
    • <a href="#ai-powered-workflow-execution"><b>AI Demo</b></a>
    • <a href="#-contributing"><b>Contributing</b></a>
    • <a href="#%EF%B8%8F-roadmap"><b>Roadmap</b></a>
  </sub>
</p>

---

## 🚀 Overview

**FuzzForge** helps security researchers and engineers automate **application security** and **offensive security** workflows with the power of AI and fuzzing frameworks.

- Orchestrate static & dynamic analysis
- Automate vulnerability research
- Scale AppSec testing with AI agents
- Build, share & reuse workflows across teams

FuzzForge is **open source**, built to empower security teams, researchers, and the community.

> 🚧 FuzzForge is under active development. Expect breaking changes.

---

## ⭐ Support the Project

<a href="https://github.com/FuzzingLabs/fuzzforge_ai/stargazers">
  <img src="https://img.shields.io/github/stars/FuzzingLabs/fuzzforge_ai?style=social" alt="GitHub Stars">
</a>

If you find FuzzForge useful, please star the repo to support development 🚀

---

## ✨ Key Features

- 🤖 **AI Agents for Security** – Specialized agents for AppSec, reversing, and fuzzing
- 🛠 **Workflow Automation** – Define & execute AppSec workflows as code
- 📈 **Vulnerability Research at Scale** – Rediscover 1-days & find 0-days with automation
- 🔗 **Fuzzer Integration** – AFL, Honggfuzz, AFLnet, StateAFL & more
- 🌐 **Community Marketplace** – Share workflows, corpora, PoCs, and modules
- 🔒 **Enterprise Ready** – Team/Corp cloud tiers for scaling offensive security

---

## 📦 Installation

### Requirements

**Python 3.11+**
Python 3.11 or higher is required.

**uv Package Manager**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Docker**
For containerized workflows, see the [Docker Installation Guide](https://docs.docker.com/get-docker/).

#### Configure AI Agent API Keys (Optional)

For AI-powered workflows, configure your LLM API keys:

```bash
cp volumes/env/.env.example volumes/env/.env
# Edit volumes/env/.env and add your API keys (OpenAI, Anthropic, Google, etc.)
```

This is required for:
- `llm_secret_detection` workflow
- AI agent features (`ff ai agent`)

Basic security workflows (gitleaks, trufflehog, security_assessment) work without this configuration.

### CLI Installation

After installing the requirements, install the FuzzForge CLI:

```bash
# Clone the repository
git clone https://github.com/fuzzinglabs/fuzzforge_ai.git
cd fuzzforge_ai

# Install CLI with uv (from the root directory)
uv tool install --python python3.12 .
```

---

## ⚡ Quickstart

Run your first workflow with **Temporal orchestration** and **automatic file upload**:

```bash
# 1. Clone the repo
git clone https://github.com/fuzzinglabs/fuzzforge_ai.git
cd fuzzforge_ai

# 2. Start FuzzForge with Temporal
docker compose up -d
```

> The first launch can take 2-3 minutes for services to initialize ☕

```bash
# 3. Run your first workflow (files are automatically uploaded)
cd test_projects/vulnerable_app/
fuzzforge init                           # Initialize FuzzForge project
ff workflow run security_assessment .    # Start workflow - CLI uploads files automatically!

# The CLI will:
# - Detect the local directory
# - Create a compressed tarball
# - Upload to backend (via MinIO)
# - Start the workflow on vertical worker
```

**What's running:**
- **Temporal**: Workflow orchestration (UI at http://localhost:8233)
- **MinIO**: File storage for targets (Console at http://localhost:9001)
- **Vertical Workers**: Pre-built workers with security toolchains
- **Backend API**: FuzzForge REST API (http://localhost:8000)

### Manual Workflow Setup

![Manual Workflow Demo](docs/static/videos/manual_workflow.gif)

_Setting up and running security workflows through the interface_

👉 More installation options in the [Documentation](https://docs.fuzzforge.ai).

---

## AI-Powered Workflow Execution

![LLM Workflow Demo](docs/static/videos/llm_workflow.gif)

_AI agents automatically analyzing code and providing security insights_

## 📚 Resources

- 🌐 [Website](https://fuzzforge.ai)
- 📖 [Documentation](https://docs.fuzzforge.ai)
- 💬 [Community Discord](https://discord.com/invite/acqv9FVG)
- 🎓 [FuzzingLabs Academy](https://academy.fuzzinglabs.com/?coupon=GITHUB_FUZZFORGE)

---

## 🤝 Contributing

We welcome contributions from the community!  
There are many ways to help:

- Report bugs by opening an [issue](../../issues)
- Suggest new features or improvements
- Submit pull requests with fixes or enhancements
- Share workflows, corpora, or modules with the community

See our [Contributing Guide](CONTRIBUTING.md) for details.

---

## 🗺️ Roadmap

Planned features and improvements:

- 📦 Public workflow & module marketplace
- 🤖 New specialized AI agents (Rust, Go, Android, Automotive)
- 🔗 Expanded fuzzer integrations (LibFuzzer, Jazzer, more network fuzzers)
- ☁️ Multi-tenant SaaS platform with team collaboration
- 📊 Advanced reporting & analytics

👉 Follow updates in the [GitHub issues](../../issues) and [Discord](https://discord.com/invite/acqv9FVG).

---

## 📜 License

FuzzForge is released under the **Business Source License (BSL) 1.1**, with an automatic fallback to **Apache 2.0** after 4 years.  
See [LICENSE](LICENSE) and [LICENSE-APACHE](LICENSE-APACHE) for details.
