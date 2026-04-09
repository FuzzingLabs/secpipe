# SecPipe MCP

Model Context Protocol (MCP) server that enables AI agents to orchestrate SecPipe security research modules.

## Overview

SecPipe MCP provides a standardized interface for AI agents (Claude Code, GitHub Copilot, Claude Desktop) to:

- List and discover available security modules
- Execute modules in isolated containers
- Chain modules together in workflows
- Manage project assets and results

The server communicates with AI agents using the [Model Context Protocol](https://modelcontextprotocol.io/) over stdio.

## Installation

### Automatic Installation (Recommended)

Use the SecPipe CLI to automatically configure MCP for your AI agent:

```bash
# For GitHub Copilot
uv run secpipe mcp install copilot

# For Claude Code (VS Code extension)
uv run secpipe mcp install claude-code

# For Claude Desktop (standalone app)
uv run secpipe mcp install claude-desktop

# Verify installation
uv run secpipe mcp status
```

After installation, restart your AI agent to activate the connection.

### Manual Installation

For custom setups, you can manually configure the MCP server.

#### Claude Code (`.mcp.json` in project root)

```json
{
  "mcpServers": {
    "secpipe": {
      "command": "/path/to/secpipe_ai/.venv/bin/python",
      "args": ["-m", "secpipe_mcp"],
      "cwd": "/path/to/secpipe_ai",
      "env": {
        "SECPIPE_MODULES_PATH": "/path/to/secpipe_ai/secpipe-modules",
        "SECPIPE_ENGINE__TYPE": "docker"
      }
    }
  }
}
```

#### GitHub Copilot (`~/.config/Code/User/mcp.json`)

```json
{
  "servers": {
    "secpipe": {
      "type": "stdio",
      "command": "/path/to/secpipe_ai/.venv/bin/python",
      "args": ["-m", "secpipe_mcp"],
      "cwd": "/path/to/secpipe_ai",
      "env": {
        "SECPIPE_MODULES_PATH": "/path/to/secpipe_ai/secpipe-modules",
        "SECPIPE_ENGINE__TYPE": "docker"
      }
    }
  }
}
```

#### Claude Desktop (`~/.config/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "secpipe": {
      "type": "stdio",
      "command": "/path/to/secpipe_ai/.venv/bin/python",
      "args": ["-m", "secpipe_mcp"],
      "cwd": "/path/to/secpipe_ai",
      "env": {
        "SECPIPE_MODULES_PATH": "/path/to/secpipe_ai/secpipe-modules",
        "SECPIPE_ENGINE__TYPE": "docker"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `SECPIPE_MODULES_PATH` | Yes | - | Path to the modules directory |
| `SECPIPE_ENGINE__TYPE` | No | `docker` | Container engine (`docker` or `podman`) |
| `SECPIPE_ENGINE__GRAPHROOT` | No | - | Container storage path (Podman under Snap only) |
| `SECPIPE_ENGINE__RUNROOT` | No | - | Container runtime state path (Podman under Snap only) |

## Available Tools

The MCP server exposes the following tools to AI agents:

### Project Management

- **`init_project`** - Initialize a new SecPipe project
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

Once configured, AI agents can interact with SecPipe naturally:

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
uv run python -m secpipe_mcp

# Run HTTP server for testing (not for production)
uv run uvicorn secpipe_mcp.application:app --reload
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
│       SecPipe MCP Server                │
│  Tools: init_project, list_modules,     │
│         execute_module, execute_workflow│
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│       SecPipe Runner                    │
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

- [SecPipe Main README](../README.md) - Overall project documentation
- [Module SDK](../secpipe-modules/secpipe-modules-sdk/README.md) - Creating custom modules
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
