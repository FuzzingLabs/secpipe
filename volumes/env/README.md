# FuzzForge LiteLLM Proxy Configuration

This directory contains configuration for the LiteLLM proxy with model-agnostic virtual keys.

## Quick Start (Fresh Clone)

### 1. Create Your `.env` File

```bash
cp .env.template .env
```

### 2. Add Your Provider API Keys

Edit `.env` and add your **real** API keys:

```bash
LITELLM_OPENAI_API_KEY=sk-proj-YOUR-OPENAI-KEY-HERE
LITELLM_ANTHROPIC_API_KEY=sk-ant-api03-YOUR-ANTHROPIC-KEY-HERE
```

### 3. Start Services

```bash
cd ../..  # Back to repo root
COMPOSE_PROFILES=secrets docker compose up -d
```

Bootstrap will automatically:
- Generate 3 virtual keys with individual budgets
- Write them to your `.env` file
- No model restrictions (model-agnostic)

## Files

- **`.env.template`** - Clean template (checked into git)
- **`.env`** - Your real keys (git ignored, you create this)
- **`.env.example`** - Legacy example

## Virtual Keys (Auto-Generated)

Bootstrap creates 3 keys with budget controls:

| Key | Budget | Duration | Used By |
|-----|--------|----------|---------|
| `OPENAI_API_KEY` | $100 | 30 days | CLI, SDK |
| `TASK_AGENT_API_KEY` | $25 | 30 days | Task Agent |
| `COGNEE_API_KEY` | $50 | 30 days | Cognee |

All keys are **model-agnostic** by default (no restrictions).

## Using Models

Registered models in `volumes/litellm/proxy_config.yaml`:
- `gpt-5-mini` → `openai/gpt-5-mini`
- `claude-sonnet-4-5` → `anthropic/claude-sonnet-4-5-20250929`
- `text-embedding-3-large` → `openai/text-embedding-3-large`

### Use Registered Aliases:

```bash
fuzzforge workflow run llm_secret_detection . -n llm_model=gpt-5-mini
fuzzforge workflow run llm_secret_detection . -n llm_model=claude-sonnet-4-5
```

### Use Any Model (Direct):

```bash
# Works without registering first!
fuzzforge workflow run llm_secret_detection . -n llm_model=openai/gpt-5-nano
```

## Proxy UI

http://localhost:10999/ui
- User: `fuzzforge` / Pass: `fuzzforge123`

## Troubleshooting

```bash
# Check bootstrap logs
docker compose logs llm-proxy-bootstrap

# Verify keys generated
grep "API_KEY=" .env | grep -v "^#" | grep -v "your-"

# Restart services
docker compose restart llm-proxy task-agent
```
