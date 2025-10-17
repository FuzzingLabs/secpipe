# FuzzForge AI Reference: CLI, Environment, and API

Welcome to the FuzzForge AI Reference! This document provides a comprehensive, no-nonsense guide to all the commands, environment variables, and API endpoints you’ll need to master the FuzzForge AI system. Use this as your quick lookup for syntax, options, and integration details.

---

## CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/register <url>` | Register an A2A agent | `/register http://localhost:10201` |
| `/unregister <name>` | Remove a registered agent | `/unregister CalculatorAgent` |
| `/list` | Show all registered agents | `/list` |
| `/memory [action]` | Knowledge graph operations | `/memory search security` |
| `/recall <query>` | Search conversation history | `/recall past calculations` |
| `/artifacts [id]` | List or view artifacts | `/artifacts artifact_abc123` |
| `/tasks [id]` | Show task status | `/tasks task_001` |
| `/skills` | Display FuzzForge skills | `/skills` |
| `/sessions` | List active sessions | `/sessions` |
| `/sendfile <agent> <path>` | Send file to agent | `/sendfile Analyzer ./code.py` |
| `/clear` | Clear the screen | `/clear` |
| `/help` | Show help | `/help` |
| `/quit` | Exit the CLI | `/quit` |

---

## Built-in Function Tools

### Knowledge Management
```python
search_project_knowledge(query, dataset, search_type)
list_project_knowledge()
ingest_to_dataset(content, dataset)
```

### File Operations
```python
list_project_files(path, pattern)
read_project_file(file_path, max_lines)
search_project_files(search_pattern, file_pattern, path)
```

### Agent Management
```python
get_agent_capabilities(agent_name)
send_file_to_agent(agent_name, file_path, note)
```

### FuzzForge Platform
```python
list_fuzzforge_workflows()
submit_security_scan_mcp(workflow_name, target_path, parameters)
get_comprehensive_scan_summary(run_id)
get_fuzzforge_run_status(run_id)
get_fuzzforge_summary(run_id)
get_fuzzforge_findings(run_id)
```

### Task Management
```python
create_task_list(tasks)
update_task_status(task_list_id, task_id, status)
get_task_list(task_list_id)
```

---

## Environment Variables

Set these in `.fuzzforge/.env` to configure your FuzzForge AI instance.

### Model Configuration
```env
LITELLM_MODEL=gpt-4o-mini          # Any LiteLLM-supported model
OPENAI_API_KEY=sk-...              # API key for model provider
ANTHROPIC_API_KEY=sk-ant-...       # For Claude models
GEMINI_API_KEY=...                 # For Gemini models
```

### Memory & Persistence
```env
SESSION_PERSISTENCE=sqlite         # sqlite|inmemory
SESSION_DB_PATH=./fuzzforge_sessions.db
MEMORY_SERVICE=inmemory            # inmemory|vertexai
```

### Server & Communication
```env
FUZZFORGE_PORT=10100               # A2A server port
ARTIFACT_STORAGE=inmemory          # inmemory|gcs
GCS_ARTIFACT_BUCKET=artifacts      # For GCS storage
```

### Debug & Observability
```env
FUZZFORGE_DEBUG=1                  # Enable debug logging
AGENTOPS_API_KEY=...               # Optional observability
```

### Platform Integration
```env
FUZZFORGE_MCP_URL=http://localhost:8010/mcp
```

---

## MCP (Model Context Protocol) Integration

FuzzForge supports the Model Context Protocol (MCP), allowing LLM clients and AI assistants to interact directly with the security testing platform. All FastAPI endpoints are available as MCP-compatible tools, making security automation accessible to any MCP-aware client.

### MCP Endpoints

- **HTTP MCP endpoint:** `http://localhost:8010/mcp`
- **SSE (Server-Sent Events):** `http://localhost:8010/mcp/sse`
- **Base API:** `http://localhost:8000`

### MCP Tools

- `submit_security_scan_mcp` — Submit security scanning workflows
- `get_comprehensive_scan_summary` — Get detailed scan analysis with recommendations

### FastAPI Endpoints (now MCP tools)

- `GET /` — API status
- `GET /workflows/` — List available workflows
- `POST /workflows/{workflow_name}/submit` — Submit security scans
- `GET /runs/{run_id}/status` — Check scan status
- `GET /runs/{run_id}/findings` — Get scan results
- `GET /fuzzing/{run_id}/stats` — Fuzzing statistics

### Usage Example: Submit a Security Scan via MCP

```json
{
  "tool": "submit_security_scan_mcp",
  "parameters": {
    "workflow_name": "security_assessment",
    "target_path": "/path/to/your/project",
    "parameters": {
      "scanner_config": {
        "patterns": ["*"],
        "check_sensitive": true
      },
      "analyzer_config": {
        "file_extensions": [".py", ".js"],
        "check_secrets": true
      }
    }
  }
}
```

### Usage Example: Get a Comprehensive Scan Summary

```json
{
  "tool": "get_comprehensive_scan_summary",
  "parameters": {
    "run_id": "your-run-id-here"
  }
}
```

### Available Workflows

**Production-ready:**
1. **security_assessment** — Comprehensive security analysis (secrets, SQL, dangerous functions)
2. **gitleaks_detection** — Pattern-based secret scanning
3. **trufflehog_detection** — Pattern-based secret scanning
4. **llm_secret_detection** — AI-powered secret detection (requires API key)

**In development:**
- **atheris_fuzzing** — Python fuzzing
- **cargo_fuzzing** — Rust fuzzing
- **ossfuzz_campaign** — OSS-Fuzz integration

### MCP Client Configuration Example

```json
{
  "mcpServers": {
    "fuzzforge": {
      "command": "curl",
      "args": ["-X", "POST", "http://localhost:8010/mcp"],
      "env": {}
    }
  }
}
```

### Troubleshooting MCP

- **MCP Connection Failed:**
  Check backend status:
  `docker compose ps fuzzforge-backend`
  `curl http://localhost:8000/health`

- **Workflows Not Found:**
  `curl http://localhost:8000/workflows/`

- **Scan Submission Errors:**
  `curl -X POST http://localhost:8000/workflows/security_assessment/submit -H "Content-Type: application/json" -d '{"target_path": "/your/path"}'`

- **General Support:**
  - Check Docker Compose logs: `docker compose logs fuzzforge-backend`
  - Verify MCP endpoint: `curl http://localhost:8010/mcp`
  - Test FastAPI endpoints directly before using MCP

For more, see the [How-To: MCP Integration](../how-to/mcp-integration.md).

---

## API Endpoints

When running as an A2A server (`python -m fuzzforge_ai --port 10100`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | Agent capabilities |
| `/` | POST | A2A message processing |
| `/artifacts/{artifact_id}` | GET | Artifact file serving |
| `/health` | GET | Health check |

### Example: Agent Card Format

```json
{
  "name": "FuzzForge",
  "description": "Multi-agent orchestrator with memory and security tools",
  "version": "1.0.0",
  "url": "http://localhost:10100",
  "protocolVersion": "0.3.0",
  "preferredTransport": "JSONRPC",
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["text/plain", "application/json"],
  "capabilities": {
    "streaming": false,
    "pushNotifications": true,
    "multiTurn": true,
    "contextRetention": true
  },
  "skills": [
    {
      "id": "orchestration",
      "name": "Agent Orchestration",
      "description": "Route requests to appropriate agents",
      "tags": ["orchestration", "routing"]
    }
  ]
}
```

### Example: A2A Message Format

```json
{
  "id": "msg_001",
  "method": "agent.invoke",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {
          "type": "text",
          "content": "Calculate factorial of 10"
        }
      ]
    },
    "context": {
      "sessionId": "session_abc123",
      "conversationId": "conv_001"
    }
  }
}
```

---

## Project Structure Reference

```
project_root/
├── .fuzzforge/                   # Project-local config
│   ├── .env                      # Environment variables
│   ├── config.json               # Project configuration
│   ├── agents.yaml               # Registered agents
│   ├── sessions.db               # Session storage
│   ├── artifacts/                # Local artifact cache
│   └── data/                     # Knowledge graphs
└── your_project_files...
```

### Agent Registry Example (`agents.yaml`)
```yaml
registered_agents:
  - name: CalculatorAgent
    url: http://localhost:10201
    description: Mathematical calculations
  - name: SecurityAnalyzer
    url: http://localhost:10202
    description: Code security analysis
```

---

## Quick Troubleshooting

- **Agent Registration Fails:** Check agent is running and accessible at its URL.
- **Memory Not Persisting:** Ensure `SESSION_PERSISTENCE=sqlite` and DB path is correct.
- **Files Not Found:** Use paths relative to project root.
- **Model API Errors:** Verify API key and model name.
