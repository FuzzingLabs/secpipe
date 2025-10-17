# How-To: Integrate and Use MCP (Model Context Protocol) with FuzzForge

FuzzForge supports the Model Context Protocol (MCP), enabling LLM clients and AI assistants to interact directly with the security testing platform. This guide walks you through setting up, connecting, and using MCP with FuzzForge for automated security scans, results analysis, and intelligent recommendations.

---

## 🚀 What is MCP?

**MCP (Model Context Protocol)** is a standard that allows AI models and clients (like Claude, GPT, or custom agents) to interact with backend tools and APIs in a structured, tool-oriented way. With FuzzForge’s MCP integration, all FastAPI endpoints become MCP-compatible tools, making security automation accessible to any MCP-aware client.

---

## 1. Prerequisites

- FuzzForge installed and running (see [Getting Started](../tutorial/getting-started.md))
- Docker and Docker Compose installed (for containerized deployment)
- An MCP-compatible client (LLM, custom agent, or CLI tool)

---

## 2. Start FuzzForge with MCP Support

From your project root, launch the platform using Docker Compose:

```bash
docker compose up -d
```

This starts the backend API and the MCP gateway.

---

## 3. Verify MCP Integration

Check that the API and MCP endpoints are live:

```bash
# API status
curl http://localhost:8000/

# List available OpenAPI endpoints (now MCP-enabled)
curl http://localhost:8000/openapi.json | jq '.paths | keys'

# MCP HTTP endpoint
curl http://localhost:8010/mcp
```

You should see status responses and endpoint listings.

---

## 4. MCP Endpoints and Tools

### MCP Endpoints

- **HTTP MCP endpoint:** `http://localhost:8010/mcp`
- **SSE (Server-Sent Events):** `http://localhost:8010/mcp/sse`
- **Base API:** `http://localhost:8000`

### FastAPI Endpoints (now MCP tools)

- `GET /` — API status
- `GET /workflows/` — List available workflows
- `POST /workflows/{workflow_name}/submit` — Submit security scans
- `GET /runs/{run_id}/status` — Check scan status
- `GET /runs/{run_id}/findings` — Get scan results
- `GET /fuzzing/{run_id}/stats` — Fuzzing statistics

### MCP-Specific Tools

- `submit_security_scan_mcp` — Submit security scanning workflows
- `get_comprehensive_scan_summary` — Get detailed scan analysis with recommendations

---

## 5. Usage Examples

### Example 1: Submit a Security Scan via MCP

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
        "file_extensions": [".py", ".js", ".java"],
        "check_secrets": true,
        "check_sql": true
      }
    }
  }
}
```

### Example 2: Get a Comprehensive Scan Summary

```json
{
  "tool": "get_comprehensive_scan_summary",
  "parameters": {
    "run_id": "your-run-id-here"
  }
}
```

---

## 6. Available Workflows

You can trigger these production-ready workflows via MCP:

1. **security_assessment** — Comprehensive security analysis (secrets, SQL, dangerous functions)
2. **gitleaks_detection** — Pattern-based secret scanning
3. **trufflehog_detection** — Pattern-based secret scanning
4. **llm_secret_detection** — AI-powered secret detection (requires API key)

Development workflows (early stages):
- **atheris_fuzzing** — Python fuzzing
- **cargo_fuzzing** — Rust fuzzing
- **ossfuzz_campaign** — OSS-Fuzz integration

List all workflows:

```bash
curl http://localhost:8000/workflows/
```

---

## 7. MCP Client Configuration

For clients that require config files, use:

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

---

## 8. Integration Benefits

- **AI-Powered Security Testing:** LLMs can submit scans, interpret findings, and provide recommendations.
- **Direct API Access:** All FastAPI endpoints are available as MCP tools.
- **Real-Time Results:** Stream scan progress and results to AI clients.
- **Intelligent Analysis:** AI can generate reports, prioritize vulnerabilities, and track improvements.

---

## 9. Advanced Usage

- **Custom MCP Tools:** Enhanced tools provide intelligent summarization, contextual recommendations, and progress tracking.
- **Docker Compose Integration:** MCP tools work seamlessly in containerized environments with automatic service discovery and volume mapping.
- **Health Monitoring:** MCP clients can verify system health via `/health` endpoints.

---

## 10. Troubleshooting

### MCP Connection Failed

```bash
# Check backend status
docker compose ps fuzzforge-backend
curl http://localhost:8000/health
```

### Workflows Not Found

```bash
curl http://localhost:8000/workflows/
```

### Scan Submission Errors

```bash
curl -X POST http://localhost:8000/workflows/infrastructure_scan/submit \
  -H "Content-Type: application/json" \
  -d '{"target_path": "/your/path"}'
```

### General Support

- Check Docker Compose logs: `docker compose logs fuzzforge-backend`
- Verify MCP endpoint: `curl http://localhost:8010/mcp`
- Test FastAPI endpoints directly before using MCP

---

## 11. Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │───▶│   FastMCP        │───▶│   FuzzForge     │
│   (LLM/AI)      │    │   Integration    │    │   API           │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   MCP Tools      │    │   Temporal       │
                       │   - scan submit  │    │   Workflows     │
                       │   - results      │    │   - Security    │
                       │   - analysis     │    │   - Fuzzing     │
                       └──────────────────┘    └─────────────────┘
```

---

## 12. Further Reading

- [Reference: CLI and API](../reference/cli-ai.md)
- [How-To: Create a Custom Workflow](./create-workflow.md)
- [FuzzForge Concepts](../concept/fuzzforge-ai.md)

---

With MCP, FuzzForge becomes a powerful, AI-friendly security automation platform. Connect your favorite LLM, automate security scans, and get actionable insights—all with a few API calls!
