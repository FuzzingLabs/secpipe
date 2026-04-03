<h1 align="center">SecPipe</h1>
<h3 align="center">AI-Powered Security Research Orchestration via MCP</h3>

<p align="center">
  <a href="https://discord.gg/8XEX33UUwZ"><img src="https://img.shields.io/discord/1420767905255133267?logo=discord&label=Discord" alt="Discord"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL%201.1-blue" alt="License: BSL 1.1"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+"/></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-green" alt="MCP Compatible"/></a>
  <a href="https://fuzzforge.ai"><img src="https://img.shields.io/badge/Website-fuzzforge.ai-purple" alt="Website"/></a>
</p>

<p align="center">
  <strong>Let AI agents orchestrate your security research workflows locally</strong>
</p>

<p align="center">
  <sub>
    <a href="#-overview"><b>Overview</b></a> •
    <a href="#-features"><b>Features</b></a> •
    <a href="#-mcp-security-hub"><b>Security Hub</b></a> •
    <a href="#-installation"><b>Installation</b></a> •
    <a href="USAGE.md"><b>Usage Guide</b></a> •
    <a href="#-contributing"><b>Contributing</b></a>
  </sub>
</p>

---

> 🚧 **FuzzForge AI is under active development.** Expect breaking changes and new features!

---

## 🚀 Overview

**FuzzForge AI** is an open-source MCP server that enables AI agents (GitHub Copilot, Claude, etc.) to orchestrate security research workflows through the **Model Context Protocol (MCP)**.

FuzzForge connects your AI assistant to **MCP tool hubs** — collections of containerized security tools that the agent can discover, chain, and execute autonomously. Instead of manually running security tools, describe what you want and let your AI assistant handle it.

### The Core: Hub Architecture

FuzzForge acts as a **meta-MCP server** — a single MCP endpoint that gives your AI agent access to tools from multiple MCP hub servers. Each hub server is a containerized security tool (Binwalk, YARA, Radare2, Nmap, etc.) that the agent can discover at runtime.

- **🔍 Discovery**: The agent lists available hub servers and discovers their tools
- **🤖 AI-Native**: Hub tools provide agent context — usage tips, workflow guidance, and domain knowledge
- **🔗 Composable**: Chain tools from different hubs into automated pipelines
- **📦 Extensible**: Add your own MCP servers to the hub registry

### 🎬 Use Case: Firmware Vulnerability Research

> **Scenario**: Analyze a firmware image to find security vulnerabilities — fully automated by an AI agent.

```
User: "Search for vulnerabilities in firmware.bin"

Agent → Binwalk:  Extract filesystem from firmware image
Agent → YARA:     Scan extracted files for vulnerability patterns
Agent → Radare2:  Trace dangerous function calls in prioritized binaries
Agent → Report:   8 vulnerabilities found (2 critical, 4 high, 2 medium)
```

### 🎬 Use Case: Rust Fuzzing Pipeline

> **Scenario**: Fuzz a Rust crate to discover vulnerabilities using AI-assisted harness generation and parallel fuzzing.

```
User: "Fuzz the blurhash crate for vulnerabilities"

Agent → Rust Analyzer:  Identify fuzzable functions and attack surface
Agent → Harness Gen:    Generate and validate fuzzing harnesses
Agent → Cargo Fuzzer:   Run parallel coverage-guided fuzzing sessions
Agent → Crash Analysis:  Deduplicate and triage discovered crashes
```

---

## ⭐ Support the Project

If you find FuzzForge useful, please **star the repo** to support development! 🚀

<a href="https://github.com/FuzzingLabs/fuzzforge_ai/stargazers">
  <img src="https://img.shields.io/github/stars/FuzzingLabs/fuzzforge_ai?style=social" alt="GitHub Stars">
</a>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Native** | Built for MCP — works with GitHub Copilot, Claude, and any MCP-compatible agent |
| 🔌 **Hub System** | Connect to MCP tool hubs — each hub brings dozens of containerized security tools |
| 🔍 **Tool Discovery** | Agents discover available tools at runtime with built-in usage guidance |
| 🔗 **Pipelines** | Chain tools from different hubs into automated multi-step workflows |
| 🔄 **Persistent Sessions** | Long-running tools (Radare2, fuzzers) with stateful container sessions |
| 🏠 **Local First** | All execution happens on your machine — no cloud required |
| 🔒 **Sandboxed** | Every tool runs in an isolated container via Docker or Podman |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Agent (Copilot/Claude)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MCP Protocol (stdio)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FuzzForge MCP Server                        │
│                                                                 │
│  Projects          Hub Discovery         Hub Execution          │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │init_project  │  │list_hub_servers  │  │execute_hub_tool   │  │
│  │set_assets    │  │discover_hub_tools│  │start_hub_server   │  │
│  │list_results  │  │get_tool_schema   │  │stop_hub_server    │  │
│  └──────────────┘  └──────────────────┘  └───────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Docker/Podman
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Hub Servers                             │
│                                                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │ Binwalk   │  │   YARA    │  │ Radare2   │  │   Nmap    │   │
│  │  6 tools  │  │  5 tools  │  │ 32 tools  │  │  8 tools  │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │ Nuclei    │  │  SQLMap   │  │  Trivy    │  │   ...     │   │
│  │  7 tools  │  │  8 tools  │  │  7 tools  │  │  36 hubs  │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 MCP Security Hub

FuzzForge ships with built-in support for the **[MCP Security Hub](https://github.com/FuzzingLabs/mcp-security-hub)** — a collection of 36 production-ready, Dockerized MCP servers covering offensive security:

| Category | Servers | Examples |
|----------|---------|----------|
| 🔍 **Reconnaissance** | 8 | Nmap, Masscan, Shodan, WhatWeb |
| 🌐 **Web Security** | 6 | Nuclei, SQLMap, ffuf, Nikto |
| 🔬 **Binary Analysis** | 6 | Radare2, Binwalk, YARA, Capa, Ghidra |
| ⛓️ **Blockchain** | 3 | Medusa, Solazy, DAML Viewer |
| ☁️ **Cloud Security** | 3 | Trivy, Prowler, RoadRecon |
| 💻 **Code Security** | 1 | Semgrep |
| 🔑 **Secrets Detection** | 1 | Gitleaks |
| 💥 **Exploitation** | 1 | SearchSploit |
| 🎯 **Fuzzing** | 2 | Boofuzz, Dharma |
| 🕵️ **OSINT** | 2 | Maigret, DNSTwist |
| 🛡️ **Threat Intel** | 2 | VirusTotal, AlienVault OTX |
| 🏰 **Active Directory** | 1 | BloodHound |

> 185+ individual tools accessible through a single MCP connection.

The hub is open source and can be extended with your own MCP servers. See the [mcp-security-hub repository](https://github.com/FuzzingLabs/mcp-security-hub) for details.

---

## 📦 Installation

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **Docker** ([Install Docker](https://docs.docker.com/get-docker/)) or Podman

### Quick Install

```bash
# Clone the repository
git clone https://github.com/FuzzingLabs/fuzzforge_ai.git
cd fuzzforge_ai

# Install dependencies
uv sync
```

### Link the Security Hub

```bash
# Clone the MCP Security Hub
git clone https://github.com/FuzzingLabs/mcp-security-hub.git ~/.fuzzforge/hubs/mcp-security-hub

# Build the Docker images for the hub tools
./scripts/build-hub-images.sh
```

Or use the terminal UI (`uv run fuzzforge ui`) to link hubs interactively.

### Configure MCP for Your AI Agent

```bash
# For GitHub Copilot
uv run fuzzforge mcp install copilot

# For Claude Code (CLI)
uv run fuzzforge mcp install claude-code

# For Claude Desktop (standalone app)
uv run fuzzforge mcp install claude-desktop

# Verify installation
uv run fuzzforge mcp status
```

**Restart your editor** and your AI agent will have access to FuzzForge tools!

---

## 🧑‍💻 Usage

Once installed, just talk to your AI agent:

```
"What security tools are available?"
"Scan this firmware image for vulnerabilities"
"Analyze this binary with radare2"
"Run nuclei against https://example.com"
```

The agent will use FuzzForge to discover the right hub tools, chain them into a pipeline, and return results — all without you touching a terminal.

See the [Usage Guide](USAGE.md) for detailed setup and advanced workflows.

---

## 📁 Project Structure

```
fuzzforge_ai/
├── fuzzforge-mcp/           # MCP server — the core of FuzzForge
├── fuzzforge-cli/           # Command-line interface & terminal UI
├── fuzzforge-common/        # Shared abstractions (containers, storage)
├── fuzzforge-runner/        # Container execution engine (Docker/Podman)
├── fuzzforge-tests/         # Integration tests
├── mcp-security-hub/        # Default hub: 36 offensive security MCP servers
└── scripts/                 # Hub image build scripts
```

---

## 🤝 Contributing

We welcome contributions from the community!

- 🐛 Report bugs via [GitHub Issues](../../issues)
- 💡 Suggest features or improvements
- 🔧 Submit pull requests
- 🔌 Add new MCP servers to the [Security Hub](https://github.com/FuzzingLabs/mcp-security-hub)

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

BSL 1.1 - See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Maintained by <a href="https://fuzzinglabs.com">FuzzingLabs</a></strong>
  <br>
</p>
