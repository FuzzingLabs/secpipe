# v0.8.0 — MCP Hub Architecture

SecPipe AI v0.8.0 is a major architectural rewrite. The previous module system has been replaced by the **MCP Hub** architecture — SecPipe now acts as a meta-MCP server that connects AI agents to collections of containerized security tools, discovered and orchestrated at runtime.

---

## Highlights

### MCP Hub System

SecPipe no longer ships its own security modules. Instead, it connects to **MCP tool hubs** — registries of Dockerized MCP servers that AI agents can discover, chain, and execute autonomously.

- **Runtime tool discovery** — agents call `list_hub_servers` and `discover_hub_tools` to find available tools
- **Agent context convention** — hub tools provide built-in usage tips, workflow guidance, and domain knowledge so agents can use them without human intervention
- **Category filtering** — servers are organized by category (`binary-analysis`, `web-security`, `reconnaissance`, etc.) for efficient discovery
- **Persistent sessions** — stateful tools like Radare2 run in long-lived containers with `start_hub_server` / `stop_hub_server`
- **Volume mounts** — project assets are automatically mounted into tool containers for seamless file access
- **Continuous mode** — long-running tools (fuzzers) with real-time status via `start_continuous_hub_tool`

### MCP Security Hub Integration

Ships with built-in support for the [MCP Security Hub](https://github.com/FuzzingLabs/mcp-security-hub) — **36 production-ready MCP servers** covering:

| Category | Servers | Examples |
|----------|---------|----------|
| Reconnaissance | 8 | Nmap, Masscan, Shodan, WhatWeb |
| Web Security | 6 | Nuclei, SQLMap, ffuf, Nikto |
| Binary Analysis | 6 | Radare2, Binwalk, YARA, Capa, Ghidra |
| Blockchain | 3 | Medusa, Solazy, DAML Viewer |
| Cloud Security | 3 | Trivy, Prowler, RoadRecon |
| Code Security | 1 | Semgrep |
| Secrets Detection | 1 | Gitleaks |
| Exploitation | 1 | SearchSploit |
| Fuzzing | 2 | Boofuzz, Dharma |
| OSINT | 2 | Maigret, DNSTwist |
| Threat Intel | 2 | VirusTotal, AlienVault OTX |
| Active Directory | 1 | BloodHound |

> **185+ individual security tools** accessible through a single MCP connection.

### Terminal UI

A new interactive terminal interface (`uv run secpipe ui`) for managing hubs and agents:

- Dashboard with hub status overview
- One-click MCP server installation for GitHub Copilot, Claude Code, and Claude Desktop
- In-UI Docker image building with live log viewer
- Hub linking and registry management

---

## Breaking Changes

- The module system has been removed (`list_modules`, `execute_module`, `start_continuous_module`)
- Replaced by hub tools: `list_hub_servers`, `discover_hub_tools`, `execute_hub_tool`, `start_hub_server`, `stop_hub_server`, etc.
- `make build-modules` replaced by `./scripts/build-hub-images.sh`

---

## Other Changes

- **CI**: GitHub Actions workflows with ruff lint, mypy typecheck, and tests
- **Config**: `SECPIPE_USER_DIR` environment variable to override user-global data directory
- **Storage**: `~/.secpipe` for user-global data, `.secpipe/` in workspace for project storage
- **Docs**: README rewritten for hub-centric architecture
