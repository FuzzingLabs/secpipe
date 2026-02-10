# FuzzForge MCP

Model Context Protocol (MCP) server that enables AI agents to orchestrate FuzzForge security research modules.

## Overview

FuzzForge MCP provides a standardized interface for AI agents (Claude Code, GitHub Copilot, Claude Desktop) to:

- List and discover available security modules
- Execute modules in isolated containers
- Chain modules together in workflows
- Manage project assets and results

The server communicates with AI agents using the [Model Context Protocol](https://modelcontextprotocol.io/) over stdio.

## Installation

### Automatic Installation (Recommended)

Use the FuzzForge CLI to automatically configure MCP for your AI agent:

```bash
# For GitHub Copilot
uv run fuzzforge mcp install copilot

# For Claude Code (VS Code extension)
uv run fuzzforge mcp install claude-code

# For Claude Desktop (standalone app)
uv run fuzzforge mcp install claude-desktop

# Verify installation
uv run fuzzforge mcp status
```

After installation, restart your AI agent to activate the connection.

### Manual Installation

For custom setups, you can manually configure the MCP server.

#### Claude Code (`.mcp.json` in project root)

```json
{
  "mcpServers": {
    "fuzzforge": {
      "command": "/path/to/fuzzforge-oss/.venv/bin/python",
      "args": ["-m", "fuzzforge_mcp"],
      "cwd": "/path/to/fuzzforge-oss",
      "env": {
        "FUZZFORGE_MODULES_PATH": "/path/to/fuzzforge-oss/fuzzforge-modules",
        "FUZZFORGE_ENGINE__TYPE": "docker"
      }
    }
  }
}
```

#### GitHub Copilot (`~/.config/Code/User/mcp.json`)

```json
{
  "servers": {
    "fuzzforge": {
      "type": "stdio",
      "command": "/path/to/fuzzforge-oss/.venv/bin/python",
      "args": ["-m", "fuzzforge_mcp"],
      "cwd": "/path/to/fuzzforge-oss",
      "env": {
        "FUZZFORGE_MODULES_PATH": "/path/to/fuzzforge-oss/fuzzforge-modules",
        "FUZZFORGE_ENGINE__TYPE": "docker"
      }
    }
  }
}
```

#### Claude Desktop (`~/.config/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "fuzzforge": {
      "type": "stdio",
      "command": "/path/to/fuzzforge-oss/.venv/bin/python",
      "args": ["-m", "fuzzforge_mcp"],
      "cwd": "/path/to/fuzzforge-oss",
      "env": {
        "FUZZFORGE_MODULES_PATH": "/path/to/fuzzforge-oss/fuzzforge-modules",
        "FUZZFORGE_ENGINE__TYPE": "docker"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `FUZZFORGE_MODULES_PATH` | Yes | - | Path to the modules directory |
| `FUZZFORGE_ENGINE__TYPE` | No | `docker` | Container engine (`docker` or `podman`) |
| `FUZZFORGE_ENGINE__GRAPHROOT` | No | - | Container storage path (Podman under Snap only) |
| `FUZZFORGE_ENGINE__RUNROOT` | No | - | Container runtime state path (Podman under Snap only) |

## Available Tools

The MCP server exposes the following tools to AI agents:

### Project Management

- **`init_project`** - Initialize a new FuzzForge project
- **`set_project_assets`** - Set initial assets (source code, contracts, etc.) for the project

### Module Management

- **`list_modules`** - List all available security research modules
- **`execute_module`** - Execute a single module in an isolated container

### Workflow Management

- **`execute_workflow`** - Execute a workflow consisting of multiple chained modules

### Resources

The server also provides resources for accessing:

- Project information and configuration
- Module metadata and schemas
- Execution results and artifacts
- Workflow definitions and status

## Usage Examples

### From AI Agent (e.g., Claude Code)

Once configured, AI agents can interact with FuzzForge naturally:

```text
User: List the available security modules

AI Agent: [Calls list_modules tool]
```

```text
User: Run echidna fuzzer on my Solidity contracts

AI Agent: [Calls init_project, set_project_assets, then execute_module]
```

```text
User: Create a workflow that compiles contracts, runs slither, then echidna

AI Agent: [Calls execute_workflow with appropriate steps]
```

### Direct Testing (Development)

For testing during development, you can run the MCP server directly:

```bash
# Run MCP server in stdio mode (for AI agents)
uv run python -m fuzzforge_mcp

# Run HTTP server for testing (not for production)
uv run uvicorn fuzzforge_mcp.application:app --reload
```

## Architecture

```text
┌─────────────────────────────────────────┐
│     AI Agent (Claude/Copilot)           │
│         via MCP Protocol                │
└─────────────────────────────────────────┘
                  │
                  │ stdio/JSON-RPC
                  ▼
┌─────────────────────────────────────────┐
│       FuzzForge MCP Server              │
│  Tools: init_project, list_modules,     │
│         execute_module, execute_workflow│
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│       FuzzForge Runner                  │
│    Podman/Docker Orchestration          │
└─────────────────────────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
   [Module 1] [Module 2] [Module 3]
   Container  Container  Container
```

## Development

### Building the Package

```bash
# Install development dependencies
uv sync

# Run type checking
uv run mypy src/

# Run tests
uv run pytest
```

## See Also

- [FuzzForge Main README](../README.md) - Overall project documentation
- [Module SDK](../fuzzforge-modules/fuzzforge-modules-sdk/README.md) - Creating custom modules
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
