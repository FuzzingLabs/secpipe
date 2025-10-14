# FuzzForge AI Module

FuzzForge AI is the multi-agent layer that lets you operate the FuzzForge security platform through natural language. It orchestrates local tooling, registered Agent-to-Agent (A2A) peers, and the Temporal-powered backend while keeping long-running context in memory and project knowledge graphs.

## Quick Start

1. **Initialise a project**
   ```bash
   cd /path/to/project
   fuzzforge init
   ```
2. **Review environment settings** – copy `.fuzzforge/.env.template` to `.fuzzforge/.env`, then edit the values to match your provider. The template ships with commented defaults for OpenAI-style usage and placeholders for Cognee keys.
   ```env
   LLM_PROVIDER=openai
   LITELLM_MODEL=gpt-5-mini
   OPENAI_API_KEY=sk-your-key
   FUZZFORGE_MCP_URL=http://localhost:8010/mcp
   SESSION_PERSISTENCE=sqlite
   ```
   Optional flags you may want to enable early:
   ```env
   MEMORY_SERVICE=inmemory
   AGENTOPS_API_KEY=sk-your-agentops-key   # Enable hosted tracing
   LOG_LEVEL=INFO                          # CLI / server log level
   ```
3. **Populate the knowledge graph**
   ```bash
   fuzzforge ingest --path . --recursive
   # alias: fuzzforge rag ingest --path . --recursive
   ```
4. **Launch the agent shell**
   ```bash
   fuzzforge ai agent
   ```
   Keep the backend running (Temporal API at `FUZZFORGE_MCP_URL`) so workflow commands succeed.

## Everyday Workflow

- Run `fuzzforge ai agent` and start with `list available fuzzforge workflows` or `/memory status` to confirm everything is wired.
- Use natural prompts for automation (`run fuzzforge workflow …`, `search project knowledge for …`) and fall back to slash commands for precision (`/recall`, `/sendfile`).
- Keep `/memory datasets` handy to see which Cognee datasets are available after each ingest.
- Start the HTTP surface with `python -m fuzzforge_ai` when external agents need access to artifacts or graph queries. The CLI stays usable at the same time.
- Refresh the knowledge graph regularly: `fuzzforge ingest --path . --recursive --force` keeps responses aligned with recent code changes.

## What the Agent Can Do

- **Route requests** – automatically selects the right local tool or remote agent using the A2A capability registry.
- **Run security workflows** – list, submit, and monitor FuzzForge workflows via MCP wrappers.
- **Manage artifacts** – create downloadable files for reports, code edits, and shared attachments.
- **Maintain context** – stores session history, semantic recall, and Cognee project graphs.
- **Serve over HTTP** – expose the same agent as an A2A server using `python -m fuzzforge_ai`.

## Essential Commands

Inside `fuzzforge ai agent` you can mix slash commands and free-form prompts:

```text
/list                     # Show registered A2A agents
/register http://:10201   # Add a remote agent
/artifacts                 # List generated files
/sendfile SecurityAgent src/report.md "Please review"
You> route_to SecurityAnalyzer: scan ./backend for secrets
You> run fuzzforge workflow static_analysis_scan on ./test_projects/demo
You> search project knowledge for "temporal status" using INSIGHTS
```

Artifacts created during the conversation are served from `.fuzzforge/artifacts/` and exposed through the A2A HTTP API.

## Memory & Knowledge

The module layers three storage systems:

- **Session persistence** (SQLite or in-memory) for chat transcripts.
- **Semantic recall** via the ADK memory service for fuzzy search.
- **Cognee graphs** for project-wide knowledge built from ingestion runs.

Re-run ingestion after major code changes to keep graph answers relevant. If Cognee variables are not set, graph-specific tools automatically respond with a polite "not configured" message.

## Sample Prompts

Use these to validate the setup once the agent shell is running:

- `list available fuzzforge workflows`
- `run fuzzforge workflow static_analysis_scan on ./backend with target_branch=main`
- `show findings for that run once it finishes`
- `refresh the project knowledge graph for ./backend`
- `search project knowledge for "temporal readiness" using INSIGHTS`
- `/recall terraform secrets`
- `/memory status`
- `ROUTE_TO SecurityAnalyzer: audit infrastructure_vulnerable`

## Need More Detail?

Dive into the dedicated guides under `ai/docs/advanced/`:

- [Architecture](https://docs.fuzzforge.ai/docs/ai/intro) – High-level architecture with diagrams and component breakdowns.
- [Ingestion](https://docs.fuzzforge.ai/docs/ai/ingestion.md) – Command options, Cognee persistence, and prompt examples.
- [Configuration](https://docs.fuzzforge.ai/docs/ai/configuration.md) – LLM provider matrix, local model setup, and tracing options.
- [Prompts](https://docs.fuzzforge.ai/docs/ai/prompts.md) – Slash commands, workflow prompts, and routing tips.
- [A2A Services](https://docs.fuzzforge.ai/docs/ai/a2a-services.md) – HTTP endpoints, agent card, and collaboration flow.
- [Memory Persistence](https://docs.fuzzforge.ai/docs/ai/architecture.md#memory--persistence) – Deep dive on memory storage, datasets, and how `/memory status` inspects them.

## Development Notes

- Entry point for the CLI: `ai/src/fuzzforge_ai/cli.py`
- A2A HTTP server: `ai/src/fuzzforge_ai/a2a_server.py`
- Tool routing & workflow glue: `ai/src/fuzzforge_ai/agent_executor.py`
- Ingestion helpers: `ai/src/fuzzforge_ai/ingest_utils.py`

Install the module in editable mode (`pip install -e ai`) while iterating so CLI changes are picked up immediately.
