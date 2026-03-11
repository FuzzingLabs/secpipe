# FuzzForge AI Usage Guide

This guide covers everything you need to know to get started with FuzzForge AI — from installation to linking your first MCP hub and running security research workflows with AI.

> **FuzzForge is designed to be used with AI agents** (GitHub Copilot, Claude, etc.) via MCP.
> A terminal UI (`fuzzforge ui`) is provided for managing agents and hubs.
> The CLI is available for advanced users but the primary experience is through natural language interaction with your AI assistant.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Terminal UI](#terminal-ui)
  - [Launching the UI](#launching-the-ui)
  - [Dashboard](#dashboard)
  - [Agent Setup](#agent-setup)
  - [Hub Manager](#hub-manager)
- [MCP Hub System](#mcp-hub-system)
  - [What is an MCP Hub?](#what-is-an-mcp-hub)
  - [FuzzingLabs Security Hub](#fuzzinglabs-security-hub)
  - [Linking a Custom Hub](#linking-a-custom-hub)
  - [Building Hub Images](#building-hub-images)
- [MCP Server Configuration (CLI)](#mcp-server-configuration-cli)
  - [GitHub Copilot](#github-copilot)
  - [Claude Code (CLI)](#claude-code-cli)
  - [Claude Desktop](#claude-desktop)
- [Using FuzzForge with AI](#using-fuzzforge-with-ai)
- [CLI Reference](#cli-reference)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

> **Prerequisites:** You need [uv](https://docs.astral.sh/uv/) and [Docker](https://docs.docker.com/get-docker/) installed.
> See the [Prerequisites](#prerequisites) section for details.

```bash
# 1. Clone and install
git clone https://github.com/FuzzingLabs/fuzzforge_ai.git
cd fuzzforge_ai
uv sync

# 2. Launch the terminal UI
uv run fuzzforge ui

# 3. Press 'h' → "FuzzingLabs Hub" to clone & link the default security hub
# 4. Select an agent row and press Enter to install the MCP server for your agent
# 5. Build the Docker images for the hub tools (required before tools can run)
./scripts/build-hub-images.sh

# 6. Restart your AI agent and start talking:
#    "What security tools are available?"
#    "Scan this binary with binwalk and yara"
#    "Analyze this Rust crate for fuzzable functions"
```

Or do it entirely from the command line:

```bash
# Install MCP for your AI agent
uv run fuzzforge mcp install copilot     # For VS Code + GitHub Copilot
# OR
uv run fuzzforge mcp install claude-code # For Claude Code CLI

# Clone and link the default security hub
git clone git@github.com:FuzzingLabs/mcp-security-hub.git ~/.fuzzforge/hubs/mcp-security-hub

# Build hub tool images (required — tools only run once their image is built)
./scripts/build-hub-images.sh

# Restart your AI agent — done!
```

> **Note:** FuzzForge uses Docker by default. Podman is also supported via `--engine podman`.

---

## Prerequisites

Before installing FuzzForge AI, ensure you have:

- **Python 3.12+** — [Download Python](https://www.python.org/downloads/)
- **uv** package manager — [Install uv](https://docs.astral.sh/uv/)
- **Docker** — Container runtime ([Install Docker](https://docs.docker.com/get-docker/))
- **Git** — For cloning hub repositories

### Installing uv

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

### Installing Docker

```bash
# Linux (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect

# macOS/Windows
# Install Docker Desktop from https://docs.docker.com/get-docker/
```

> **Note:** Podman is also supported. Use `--engine podman` with CLI commands
> or set `FUZZFORGE_ENGINE=podman` environment variable.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/FuzzingLabs/fuzzforge_ai.git
cd fuzzforge_ai
```

### 2. Install Dependencies

```bash
uv sync
```

This installs all FuzzForge components in a virtual environment.

### 3. Verify Installation

```bash
uv run fuzzforge --help
```

---

## Terminal UI

FuzzForge ships with a terminal user interface (TUI) built on [Textual](https://textual.textualize.io/) for managing AI agents and MCP hub servers from a single dashboard.

### Launching the UI

```bash
uv run fuzzforge ui
```

### Dashboard

The main screen is split into two panels:

| Panel | Content |
|-------|---------|
| **AI Agents** (left) | Shows GitHub Copilot, Claude Desktop, and Claude Code with live link status and config file path |
| **Hub Servers** (right) | Shows all configured MCP hub tools with Docker image name, source hub, and build status (✓ Ready / ✗ Not built) |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | **Select** — Act on the selected row (setup/unlink an agent) |
| `h` | **Hub Manager** — Open the hub management screen |
| `r` | **Refresh** — Re-check all agent and hub statuses |
| `q` | **Quit** |

### Agent Setup

Select an agent row in the AI Agents table and press `Enter`:

- **If the agent is not linked** → a setup dialog opens asking for your container engine (Docker or Podman), then installs the FuzzForge MCP configuration
- **If the agent is already linked** → a confirmation dialog offers to unlink it (removes the `fuzzforge` entry without touching other MCP servers)

The setup auto-detects:
- FuzzForge installation root
- Docker/Podman socket path
- Hub configuration from `hub-config.json`

### Hub Manager

Press `h` to open the hub manager. This is where you manage your MCP hub repositories:

| Button | Action |
|--------|--------|
| **FuzzingLabs Hub** | One-click clone of the official [mcp-security-hub](https://github.com/FuzzingLabs/mcp-security-hub) repository — clones to `~/.fuzzforge/hubs/mcp-security-hub`, scans for tools, and registers them in `hub-config.json` |
| **Link Path** | Link any local directory as a hub — enter a name and path, FuzzForge scans it for `category/tool-name/Dockerfile` patterns |
| **Clone URL** | Clone any git repository and link it as a hub |
| **Remove** | Unlink the selected hub and remove its servers from the configuration |

The hub table shows:
- **Name** — Hub name (★ prefix for the default hub)
- **Path** — Local directory path
- **Servers** — Number of MCP tools discovered
- **Source** — Git URL or "local"

---

## MCP Hub System

### What is an MCP Hub?

An MCP hub is a directory containing one or more containerized MCP tools, organized by category:

```
my-hub/
├── category-a/
│   ├── tool-1/
│   │   └── Dockerfile
│   └── tool-2/
│       └── Dockerfile
├── category-b/
│   └── tool-3/
│       └── Dockerfile
└── ...
```

FuzzForge scans for the pattern `category/tool-name/Dockerfile` and auto-generates server configuration entries for each discovered tool.

### FuzzingLabs Security Hub

The default MCP hub is [mcp-security-hub](https://github.com/FuzzingLabs/mcp-security-hub), maintained by FuzzingLabs. It includes **40+ security tools** across categories:

| Category | Tools |
|----------|-------|
| **Reconnaissance** | nmap, masscan, shodan, zoomeye, whatweb, pd-tools, externalattacker, networksdb |
| **Binary Analysis** | binwalk, yara, capa, radare2, ghidra, ida |
| **Code Security** | semgrep, rust-analyzer, harness-tester, cargo-fuzzer, crash-analyzer |
| **Web Security** | nuclei, nikto, sqlmap, ffuf, burp, waybackurls |
| **Fuzzing** | boofuzz, dharma |
| **Exploitation** | searchsploit |
| **Secrets** | gitleaks |
| **Cloud Security** | trivy, prowler, roadrecon |
| **OSINT** | maigret, dnstwist |
| **Threat Intel** | virustotal, otx |
| **Password Cracking** | hashcat |
| **Blockchain** | medusa, solazy, daml-viewer |

**Clone it via the UI:**

1. `uv run fuzzforge ui`
2. Press `h` → click **FuzzingLabs Hub**
3. Wait for the clone to finish — servers are auto-registered

**Or clone manually:**

```bash
git clone git@github.com:FuzzingLabs/mcp-security-hub.git ~/.fuzzforge/hubs/mcp-security-hub
```

### Linking a Custom Hub

You can link any directory that follows the `category/tool-name/Dockerfile` layout:

**Via the UI:**

1. Press `h` → **Link Path**
2. Enter a name and the directory path

**Via the CLI (planned):** Not yet available — use the UI.

### Building Hub Images

After linking a hub, you need to build the Docker images before the tools can be used:

```bash
# Build all images from the default security hub
./scripts/build-hub-images.sh

# Or build a single tool image
docker build -t semgrep-mcp:latest mcp-security-hub/code-security/semgrep-mcp/
```

The dashboard hub table shows ✓ Ready for built images and ✗ Not built for missing ones.

---

## MCP Server Configuration (CLI)

If you prefer the command line over the TUI, you can configure agents directly:

### GitHub Copilot

```bash
uv run fuzzforge mcp install copilot
```

The command auto-detects:
- **FuzzForge root** — Where FuzzForge is installed
- **Docker socket** — Auto-detects `/var/run/docker.sock`

**Optional overrides:**
```bash
uv run fuzzforge mcp install copilot --engine podman
```

**After installation:** Restart VS Code. FuzzForge tools appear in GitHub Copilot Chat.

### Claude Code (CLI)

```bash
uv run fuzzforge mcp install claude-code
```

Installs to `~/.claude.json`. FuzzForge tools are available from any directory after restarting Claude.

### Claude Desktop

```bash
uv run fuzzforge mcp install claude-desktop
```

**After installation:** Restart Claude Desktop.

### Check Status

```bash
uv run fuzzforge mcp status
```

### Remove Configuration

```bash
uv run fuzzforge mcp uninstall copilot
uv run fuzzforge mcp uninstall claude-code
uv run fuzzforge mcp uninstall claude-desktop
```

---

## Using FuzzForge with AI

Once MCP is configured and hub images are built, interact with FuzzForge through natural language with your AI assistant.

### Example Conversations

**Discover available tools:**
```
You: "What security tools are available in FuzzForge?"
AI: Queries hub tools → "I found 15 tools across categories: nmap for 
    port scanning, binwalk for firmware analysis, semgrep for code 
    scanning, cargo-fuzzer for Rust fuzzing..."
```

**Analyze a binary:**
```
You: "Extract and analyze this firmware image"
AI: Uses binwalk to extract → yara for pattern matching → capa for 
    capability detection → "Found 3 embedded filesystems, 2 YARA 
    matches for known vulnerabilities..."
```

**Fuzz Rust code:**
```
You: "Analyze this Rust crate for functions I should fuzz"
AI: Uses rust-analyzer → "Found 3 fuzzable entry points..."

You: "Start fuzzing parse_input for 10 minutes"
AI: Uses cargo-fuzzer → "Fuzzing session started. 2 crashes found..."
```

**Scan for vulnerabilities:**
```
You: "Scan this codebase with semgrep for security issues"
AI: Uses semgrep-mcp → "Found 5 findings: 2 high severity SQL injection 
    patterns, 3 medium severity hardcoded secrets..."
```

---

## CLI Reference

### UI Command

```bash
uv run fuzzforge ui                      # Launch the terminal dashboard
```

### MCP Commands

```bash
uv run fuzzforge mcp status              # Check agent configuration status
uv run fuzzforge mcp install <agent>     # Install MCP config (copilot|claude-code|claude-desktop)
uv run fuzzforge mcp uninstall <agent>   # Remove MCP config
uv run fuzzforge mcp generate <agent>    # Preview config without installing
```

### Project Commands

```bash
uv run fuzzforge project init             # Initialize a project
uv run fuzzforge project info             # Show project info
uv run fuzzforge project executions       # List executions
uv run fuzzforge project results <id>     # Get execution results
```

---

## Environment Variables

Configure FuzzForge using environment variables:

```bash
# Override the FuzzForge installation root (auto-detected from cwd by default)
export FUZZFORGE_ROOT=/path/to/fuzzforge_ai

# Override the user-global data directory (default: ~/.fuzzforge)
# Useful for isolated testing without touching your real installation
export FUZZFORGE_USER_DIR=/tmp/my-fuzzforge-test

# Storage path for projects and execution results (default: <workspace>/.fuzzforge/storage)
export FUZZFORGE_STORAGE__PATH=/path/to/storage

# Container engine (Docker is default)
export FUZZFORGE_ENGINE__TYPE=docker  # or podman

# Podman-specific container storage paths
export FUZZFORGE_ENGINE__GRAPHROOT=~/.fuzzforge/containers/storage
export FUZZFORGE_ENGINE__RUNROOT=~/.fuzzforge/containers/run
```

---

## Troubleshooting

### Docker Not Running

```
Error: Cannot connect to Docker daemon
```

**Solution:**
```bash
# Linux: Start Docker service
sudo systemctl start docker

# macOS/Windows: Start Docker Desktop application

# Verify Docker is running
docker run --rm hello-world
```

### Permission Denied on Docker Socket

```
Error: Permission denied connecting to Docker socket
```

**Solution:**
```bash
sudo usermod -aG docker $USER
# Log out and back in, then verify:
docker run --rm hello-world
```

### Hub Images Not Built

The dashboard shows ✗ Not built for tools:

```bash
# Build all hub images
./scripts/build-hub-images.sh

# Or build a single tool
docker build -t <tool-name>:latest mcp-security-hub/<category>/<tool-name>/
```

### MCP Server Not Starting

```bash
# Check agent configuration
uv run fuzzforge mcp status

# Verify the config file path exists and contains valid JSON
cat ~/.config/Code/User/mcp.json    # Copilot
cat ~/.claude.json                   # Claude Code
```

### Using Podman Instead of Docker

```bash
# Install with Podman engine
uv run fuzzforge mcp install copilot --engine podman

# Or set environment variable
export FUZZFORGE_ENGINE=podman
```

### Hub Registry

FuzzForge stores linked hub information in `~/.fuzzforge/hubs.json`. If something goes wrong:

```bash
# View registry
cat ~/.fuzzforge/hubs.json

# Reset registry
rm ~/.fuzzforge/hubs.json
```

---

## Next Steps

- 🖥️ Launch `uv run fuzzforge ui` and explore the dashboard
- 🔒 Clone the [mcp-security-hub](https://github.com/FuzzingLabs/mcp-security-hub) for 40+ security tools
- 💬 Join our [Discord](https://discord.gg/8XEX33UUwZ) for support

---

<p align="center">
  <strong>Built with ❤️ by <a href="https://fuzzinglabs.com">FuzzingLabs</a></strong>
</p>
