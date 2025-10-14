# LLM & Environment Configuration

FuzzForge AI relies on LiteLLM adapters embedded in the Google ADK runtime, so you can swap between providers without touching code. Configuration is driven by environment variables inside `.fuzzforge/.env`.

## Minimal Setup

```env
LLM_PROVIDER=openai
LITELLM_MODEL=gpt-5-mini
OPENAI_API_KEY=sk-your-key
```

Set these values before launching `fuzzforge ai agent` or `python -m fuzzforge_ai`.

## .env Template

`fuzzforge init` creates `.fuzzforge/.env.template` alongside the real secrets file. Keep the template under version control so teammates can copy it to `.fuzzforge/.env` and fill in provider credentials locally. The template includes commented examples for Cognee, AgentOps, and alternative LLM providers—extend it with any project-specific overrides you expect collaborators to set.

## Provider Examples

**OpenAI-compatible (Azure, etc.)**
```env
LLM_PROVIDER=azure_openai
LITELLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your-azure-key
LLM_ENDPOINT=https://your-resource.openai.azure.com
```

**Anthropic**
```env
LLM_PROVIDER=anthropic
LITELLM_MODEL=claude-3-haiku-20240307
ANTHROPIC_API_KEY=sk-your-key
```

**Ollama (local models)**
```env
LLM_PROVIDER=ollama_chat
LITELLM_MODEL=codellama:latest
OLLAMA_API_BASE=http://localhost:11434
```
Run `ollama pull codellama:latest` ahead of time so the adapter can stream tokens immediately. Any Ollama-hosted model works; set `LITELLM_MODEL` to match the image tag.

**Vertex AI**
```env
LLM_PROVIDER=vertex_ai
LITELLM_MODEL=gemini-1.5-pro
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## Additional LiteLLM Providers

LiteLLM exposes dozens of adapters. Popular additions include:

- `LLM_PROVIDER=anthropic_messages` for Claude 3.5.
- `LLM_PROVIDER=azure_openai` for Azure-hosted GPT variants.
- `LLM_PROVIDER=groq` for Groq LPU-backed models (`GROQ_API_KEY` required).
- `LLM_PROVIDER=ollama_chat` for any local Ollama model.
- `LLM_PROVIDER=vertex_ai` for Gemini.

Refer to the [LiteLLM provider catalog](https://docs.litellm.ai/docs/providers) when mapping environment variables; each adapter lists the exact keys the ADK runtime expects.

## Session Persistence

```
SESSION_PERSISTENCE=sqlite   # sqlite | inmemory
MEMORY_SERVICE=inmemory      # ADK memory backend
```

Set `SESSION_PERSISTENCE=sqlite` to preserve conversational history across restarts. For ephemeral sessions, switch to `inmemory`.

## Knowledge Graph Settings

To enable Cognee-backed graphs:

```env
LLM_COGNEE_PROVIDER=openai
LLM_COGNEE_MODEL=gpt-5-mini
LLM_COGNEE_API_KEY=sk-your-key
```

If the Cognee variables are omitted, graph-specific tools remain available but return a friendly "not configured" response.

## MCP / Backend Integration

```env
FUZZFORGE_MCP_URL=http://localhost:8010/mcp
```

The agent uses this endpoint to list, launch, and monitor Temporal workflows.

## Tracing & Observability

The executor ships with optional AgentOps tracing. Provide an API key to record conversations, tool calls, and workflow updates:

```env
AGENTOPS_API_KEY=sk-your-agentops-key
AGENTOPS_ENVIRONMENT=local     # Optional tag for dashboards
```

Set `FUZZFORGE_DEBUG=1` to surface verbose executor logging and enable additional stdout in the CLI. For HTTP deployments, combine that with:

```env
LOG_LEVEL=DEBUG
```

The ADK runtime also honours `GOOGLE_ADK_TRACE_DIR=/path/to/logs` if you want JSONL traces without an external service.

## Debugging Flags

```env
FUZZFORGE_DEBUG=1           # Enables verbose logging
LOG_LEVEL=DEBUG             # Applies to the A2A server and CLI
```

These flags surface additional insight when diagnosing routing or ingestion issues. Combine them with AgentOps tracing to get full timelines of tool usage.

## Related Code

- Env bootstrap: `ai/src/fuzzforge_ai/config_manager.py`
- LiteLLM glue: `ai/src/fuzzforge_ai/agent.py`
- Cognee integration: `ai/src/fuzzforge_ai/cognee_service.py`
