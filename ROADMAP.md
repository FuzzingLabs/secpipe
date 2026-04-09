# SecPipe AI Roadmap

This document outlines the planned features and development direction for SecPipe AI.

---

## 🎯 Upcoming Features

### 1. MCP Security Hub Integration

**Status:** 🔄 Planned

Integrate [mcp-security-hub](https://github.com/FuzzingLabs/mcp-security-hub) tools into SecPipe, giving AI agents access to 28 MCP servers and 163+ security tools through a unified interface.

#### How It Works

Unlike native SecPipe modules (built with the SDK), mcp-security-hub tools are **standalone MCP servers**. The integration will bridge these tools so they can be:

- Discovered via `list_modules` alongside native modules
- Executed through SecPipe's orchestration layer
- Chained with native modules in workflows

| Aspect | Native Modules | MCP Hub Tools |
|--------|----------------|---------------|
| **Runtime** | SecPipe SDK container | Standalone MCP server container |
| **Protocol** | Direct execution | MCP-to-MCP bridge |
| **Configuration** | Module config | Tool-specific args |
| **Output** | SecPipe results format | Tool-native format (normalized) |

#### Goals

- Unified discovery of all available tools (native + hub)
- Orchestrate hub tools through SecPipe's workflow engine
- Normalize outputs for consistent result handling
- No modification required to mcp-security-hub tools

#### Planned Tool Categories

| Category | Tools | Example Use Cases |
|----------|-------|-------------------|
| **Reconnaissance** | nmap, masscan, whatweb, shodan | Network scanning, service discovery |
| **Web Security** | nuclei, sqlmap, ffuf, nikto | Vulnerability scanning, fuzzing |
| **Binary Analysis** | radare2, binwalk, yara, capa, ghidra | Reverse engineering, malware analysis |
| **Cloud Security** | trivy, prowler | Container scanning, cloud auditing |
| **Secrets Detection** | gitleaks | Credential scanning |
| **OSINT** | maigret, dnstwist | Username tracking, typosquatting |
| **Threat Intel** | virustotal, otx | Malware analysis, IOC lookup |

#### Example Workflow

```
You: "Scan example.com for vulnerabilities and analyze any suspicious binaries"

AI Agent:
1. Uses nmap module for port discovery
2. Uses nuclei module for vulnerability scanning
3. Uses binwalk module to extract firmware
4. Uses yara module for malware detection
5. Generates consolidated report
```

---

### 2. User Interface

**Status:** 🔄 Planned

A graphical interface to manage SecPipe without the command line.

#### Goals

- Provide an alternative to CLI for users who prefer visual tools
- Make configuration and monitoring more accessible
- Complement (not replace) the CLI experience

#### Planned Capabilities

| Capability | Description |
|------------|-------------|
| **Configuration** | Change MCP server settings, engine options, paths |
| **Module Management** | Browse, configure, and launch modules |
| **Execution Monitoring** | View running tasks, logs, progress, metrics |
| **Project Overview** | Manage projects and browse execution results |
| **Workflow Management** | Create and run multi-module workflows |

---

## 📋 Backlog

Features under consideration for future releases:

| Feature | Description |
|---------|-------------|
| **Module Marketplace** | Browse and install community modules |
| **Scheduled Executions** | Run modules on a schedule (cron-style) |
| **Team Collaboration** | Share projects, results, and workflows |
| **Reporting Engine** | Generate PDF/HTML security reports |
| **Notifications** | Slack, Discord, email alerts for findings |

---

## ✅ Completed

| Feature | Version | Date |
|---------|---------|------|
| Docker as default engine | 0.1.0 | Jan 2026 |
| MCP server for AI agents | 0.1.0 | Jan 2026 |
| CLI for project management | 0.1.0 | Jan 2026 |
| Continuous execution mode | 0.1.0 | Jan 2026 |
| Workflow orchestration | 0.1.0 | Jan 2026 |

---

## 💬 Feedback

Have suggestions for the roadmap? 

- Open an issue on [GitHub](https://github.com/FuzzingLabs/secpipe_ai/issues)
- Join our [Discord](https://discord.gg/8XEX33UUwZ)

---

<p align="center">
  <strong>Built with ❤️ by <a href="https://fuzzinglabs.com">FuzzingLabs</a></strong>
</p>
