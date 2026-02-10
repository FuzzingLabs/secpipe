# FuzzForge OSS Usage Guide

This guide covers everything you need to know to get started with FuzzForge OSS - from installation to running your first security research workflow with AI.

> **FuzzForge is designed to be used with AI agents** (GitHub Copilot, Claude, etc.) via MCP.
> The CLI is available for advanced users but the primary experience is through natural language interaction with your AI assistant.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Building Modules](#building-modules)
- [MCP Server Configuration](#mcp-server-configuration)
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
> See the [Prerequisites](#prerequisites) section for installation instructions.

```bash
# 1. Clone and install
git clone https://github.com/FuzzingLabs/fuzzforge-oss.git
cd fuzzforge-oss
uv sync

# 2. Build the module images (one-time setup)
make build-modules

# 3. Install MCP for your AI agent
uv run fuzzforge mcp install copilot  # For VS Code + GitHub Copilot
# OR
uv run fuzzforge mcp install claude-code  # For Claude Code CLI

# 4. Restart your AI agent (VS Code, Claude, etc.)

# 5. Start talking to your AI:
#    "List available FuzzForge modules"
#    "Analyze this Rust crate for fuzzable functions"
#    "Start fuzzing the parse_input function"
```

> **Note:** FuzzForge uses Docker by default. Podman is also supported via `--engine podman`.

---

## Prerequisites

Before installing FuzzForge OSS, ensure you have:

- **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
- **uv** package manager - [Install uv](https://docs.astral.sh/uv/)
- **Docker** - Container runtime ([Install Docker](https://docs.docker.com/get-docker/))

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
git clone https://github.com/FuzzingLabs/fuzzforge-oss.git
cd fuzzforge-oss
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

## Building Modules

FuzzForge modules are containerized security tools. After cloning, you need to build them once:

### Build All Modules

```bash
# From the fuzzforge-oss directory
make build-modules
```

This builds all available modules:
- `fuzzforge-rust-analyzer` - Analyzes Rust code for fuzzable functions
- `fuzzforge-cargo-fuzzer` - Runs cargo-fuzz on Rust crates
- `fuzzforge-harness-validator` - Validates generated fuzzing harnesses
- `fuzzforge-crash-analyzer` - Analyzes crash inputs

### Build a Single Module

```bash
# Build a specific module
cd fuzzforge-modules/rust-analyzer
make build
```

### Verify Modules are Built

```bash
# List built module images
docker images | grep fuzzforge
```

You should see something like:
```
fuzzforge-rust-analyzer    0.1.0    abc123def456    2 minutes ago    850 MB
fuzzforge-cargo-fuzzer     0.1.0    789ghi012jkl    2 minutes ago    1.2 GB
...
```

---

## MCP Server Configuration

FuzzForge integrates with AI agents through the Model Context Protocol (MCP). Configure your preferred AI agent to use FuzzForge tools.

### GitHub Copilot

```bash
# That's it! Just run this command:
uv run fuzzforge mcp install copilot
```

The command auto-detects everything:
- **FuzzForge root** - Where FuzzForge is installed
- **Modules path** - Defaults to `fuzzforge-oss/fuzzforge-modules`
- **Docker socket** - Auto-detects `/var/run/docker.sock`

**Optional overrides** (usually not needed):
```bash
uv run fuzzforge mcp install copilot \
  --modules /path/to/modules \
  --engine podman  # if using Podman instead of Docker
```

**After installation:**
1. Restart VS Code
2. Open GitHub Copilot Chat
3. FuzzForge tools are now available!

### Claude Code (CLI)

```bash
uv run fuzzforge mcp install claude-code
```

Installs to `~/.claude.json` so FuzzForge tools are available from any directory.

**After installation:**
1. Run `claude` from any directory
2. FuzzForge tools are now available!

### Claude Desktop

```bash
# Automatic installation
uv run fuzzforge mcp install claude-desktop

# Verify
uv run fuzzforge mcp status
```

**After installation:**
1. Restart Claude Desktop
2. FuzzForge tools are now available!

### Check MCP Status

```bash
uv run fuzzforge mcp status
```

Shows configuration status for all supported AI agents:

```
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Agent                ┃ Config Path                               ┃ Status       ┃ FuzzForge Configured    ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ GitHub Copilot       │ ~/.config/Code/User/mcp.json              │ ✓ Exists     │ ✓ Yes                   │
│ Claude Desktop       │ ~/.config/Claude/claude_desktop_config... │ Not found    │ -                       │
│ Claude Code          │ ~/.claude.json                            │ ✓ Exists     │ ✓ Yes                   │
└──────────────────────┴───────────────────────────────────────────┴──────────────┴─────────────────────────┘
```

### Generate Config Without Installing

```bash
# Preview the configuration that would be installed
uv run fuzzforge mcp generate copilot
uv run fuzzforge mcp generate claude-desktop
uv run fuzzforge mcp generate claude-code
```

### Remove MCP Configuration

```bash
uv run fuzzforge mcp uninstall copilot
uv run fuzzforge mcp uninstall claude-desktop
uv run fuzzforge mcp uninstall claude-code
```

---

## Using FuzzForge with AI

Once MCP is configured, you interact with FuzzForge through natural language with your AI assistant.

### Example Conversations

**Discover available tools:**
```
You: "What FuzzForge modules are available?"
AI: Uses list_modules → "I found 4 modules: rust-analyzer, cargo-fuzzer, 
    harness-validator, and crash-analyzer..."
```

**Analyze code for fuzzing targets:**
```
You: "Analyze this Rust crate for functions I should fuzz"
AI: Uses execute_module("rust-analyzer") → "I found 3 good fuzzing candidates:
    - parse_input() in src/parser.rs - handles untrusted input
    - decode_message() in src/codec.rs - complex parsing logic
    ..."
```

**Generate and validate harnesses:**
```
You: "Generate a fuzzing harness for the parse_input function"
AI: Creates harness code, then uses execute_module("harness-validator") 
    → "Here's a harness that compiles successfully..."
```

**Run continuous fuzzing:**
```
You: "Start fuzzing parse_input for 10 minutes"
AI: Uses start_continuous_module("cargo-fuzzer") → "Started fuzzing session abc123"

You: "How's the fuzzing going?"
AI: Uses get_continuous_status("abc123") → "Running for 5 minutes:
    - 150,000 executions
    - 2 crashes found
    - 45% edge coverage"

You: "Stop and show me the crashes"
AI: Uses stop_continuous_module("abc123") → "Found 2 unique crashes..."
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `list_modules` | List all available security modules |
| `execute_module` | Run a module once and get results |
| `start_continuous_module` | Start a long-running module (e.g., fuzzing) |
| `get_continuous_status` | Check status of a continuous session |
| `stop_continuous_module` | Stop a continuous session |
| `list_continuous_sessions` | List all active sessions |
| `get_execution_results` | Retrieve results from an execution |
| `execute_workflow` | Run a multi-step workflow |

---

## CLI Reference

> **Note:** The CLI is for advanced users. Most users should interact with FuzzForge through their AI assistant.

### MCP Commands

```bash
uv run fuzzforge mcp status              # Check configuration status
uv run fuzzforge mcp install <agent>     # Install MCP config
uv run fuzzforge mcp uninstall <agent>   # Remove MCP config
uv run fuzzforge mcp generate <agent>    # Preview config without installing
```

### Module Commands

```bash
uv run fuzzforge modules list                    # List available modules
uv run fuzzforge modules info <module>           # Show module details
uv run fuzzforge modules run <module> --assets . # Run a module
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
# Project paths
export FUZZFORGE_MODULES_PATH=/path/to/modules
export FUZZFORGE_STORAGE_PATH=/path/to/storage

# Container engine (Docker is default)
export FUZZFORGE_ENGINE__TYPE=docker  # or podman

# Podman-specific settings (only needed if using Podman under Snap)
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
# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and back in for changes to take effect
# Then verify:
docker run --rm hello-world
```

### No Modules Found

```
No modules found.
```

**Solution:**
1. Build the modules first: `make build-modules`
2. Check the modules path: `uv run fuzzforge modules list`
3. Verify images exist: `docker images | grep fuzzforge`

### MCP Server Not Starting

Check the MCP configuration:
```bash
uv run fuzzforge mcp status
```

Verify the configuration file path exists and contains valid JSON.

### Module Container Fails to Build

```bash
# Build module container manually to see errors
cd fuzzforge-modules/<module-name>
docker build -t <module-name> .
```

### Using Podman Instead of Docker

If you prefer Podman:
```bash
# Use --engine podman with CLI
uv run fuzzforge mcp install copilot --engine podman

# Or set environment variable
export FUZZFORGE_ENGINE=podman
```

### Check Logs

FuzzForge stores execution logs in the storage directory:
```bash
ls -la ~/.fuzzforge/storage/<project-id>/<execution-id>/
```

---

## Next Steps

- 📖 Read the [Module SDK Guide](fuzzforge-modules/fuzzforge-modules-sdk/README.md) to create custom modules
- 🎬 Check the demos in the [README](README.md)
- 💬 Join our [Discord](https://discord.gg/8XEX33UUwZ) for support

---

<p align="center">
  <strong>Built with ❤️ by <a href="https://fuzzinglabs.com">FuzzingLabs</a></strong>
</p>
