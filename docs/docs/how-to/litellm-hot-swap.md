---
title: "Hot-Swap LiteLLM Models"
description: "Register OpenAI and Anthropic models with the bundled LiteLLM proxy and switch them on the task agent without downtime."
---

LiteLLM sits between the task agent and upstream providers, so every model change
is just an API call. This guide walks through registering OpenAI and Anthropic
models, updating the virtual key, and exercising the A2A hot-swap flow.

## Prerequisites

- `docker compose up llm-proxy llm-proxy-db task-agent`
- Provider secrets in `volumes/env/.env`:
  - `LITELLM_OPENAI_API_KEY`
  - `LITELLM_ANTHROPIC_API_KEY`
- Master key (`LITELLM_MASTER_KEY`) and task-agent virtual key (auto-generated
  during bootstrap)

> UI access uses `UI_USERNAME` / `UI_PASSWORD` (defaults: `fuzzforge` /
> `fuzzforge123`). Change them by exporting new values before running compose.

## Register Provider Models

Use the admin API to register the models the proxy should expose. The snippet
below creates aliases for OpenAI `gpt-5`, `gpt-5-mini`, and Anthropic
`claude-sonnet-4-5`.

```bash
MASTER_KEY=$(awk -F= '$1=="LITELLM_MASTER_KEY"{print $2}' volumes/env/.env)
export OPENAI_API_KEY=$(awk -F= '$1=="OPENAI_API_KEY"{print $2}' volumes/env/.env)
python - <<'PY'
import os, requests
master = os.environ['MASTER_KEY'].strip()
base = 'http://localhost:10999'
models = [
    {
        "model_name": "openai/gpt-5",
        "litellm_params": {
            "model": "gpt-5",
            "custom_llm_provider": "openai",
            "api_key": "os.environ/LITELLM_OPENAI_API_KEY"
        },
        "model_info": {
            "provider": "openai",
            "description": "OpenAI GPT-5"
        }
    },
    {
        "model_name": "openai/gpt-5-mini",
        "litellm_params": {
            "model": "gpt-5-mini",
            "custom_llm_provider": "openai",
            "api_key": "os.environ/LITELLM_OPENAI_API_KEY"
        },
        "model_info": {
            "provider": "openai",
            "description": "OpenAI GPT-5 mini"
        }
    },
    {
        "model_name": "anthropic/claude-sonnet-4-5",
        "litellm_params": {
            "model": "claude-sonnet-4-5",
            "custom_llm_provider": "anthropic",
            "api_key": "os.environ/LITELLM_ANTHROPIC_API_KEY"
        },
        "model_info": {
            "provider": "anthropic",
            "description": "Anthropic Claude Sonnet 4.5"
        }
    }
]
for payload in models:
    resp = requests.post(
        f"{base}/model/new",
        headers={"Authorization": f"Bearer {master}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if resp.status_code not in (200, 201, 409):
        raise SystemExit(f"Failed to register {payload['model_name']}: {resp.status_code} {resp.text}")
    print(payload['model_name'], '=>', resp.status_code)
PY
```

Each entry stores the upstream secret by reference (`os.environ/...`) so the
raw API key never leaves the container environment.

## Relax Virtual Key Model Restrictions

Let the agent key call every model on the proxy:

```bash
MASTER_KEY=$(awk -F= '$1=="LITELLM_MASTER_KEY"{print $2}' volumes/env/.env)
VK=$(awk -F= '$1=="OPENAI_API_KEY"{print $2}' volumes/env/.env)
python - <<'PY'
import os, requests, json
resp = requests.post(
    'http://localhost:10999/key/update',
    headers={
        'Authorization': f"Bearer {os.environ['MASTER_KEY'].strip()}",
        'Content-Type': 'application/json'
    },
    json={'key': os.environ['VK'].strip(), 'models': []},
    timeout=60,
)
print(json.dumps(resp.json(), indent=2))
PY
```

Restart the task agent so it sees the refreshed key:

```bash
docker compose restart task-agent
```

## Hot-Swap With The A2A Helper

Switch models without restarting the service:

```bash
# Ensure the CLI reads the latest virtual key
export OPENAI_API_KEY=$(awk -F= '$1=="OPENAI_API_KEY"{print $2}' volumes/env/.env)

# OpenAI gpt-5 alias
python ai/agents/task_agent/a2a_hot_swap.py \
  --url http://localhost:10900/a2a/litellm_agent \
  --model openai gpt-5 \
  --context switch-demo

# Confirm the response comes from the new model
python ai/agents/task_agent/a2a_hot_swap.py \
  --url http://localhost:10900/a2a/litellm_agent \
  --message "Which model am I using?" \
  --context switch-demo

# Swap to gpt-5-mini
python ai/agents/task_agent/a2a_hot_swap.py --url http://localhost:10900/a2a/litellm_agent --model openai gpt-5-mini --context switch-demo

# Swap to Anthropic Claude Sonnet 4.5
python ai/agents/task_agent/a2a_hot_swap.py --url http://localhost:10900/a2a/litellm_agent --model anthropic claude-sonnet-4-5 --context switch-demo
```

> Each invocation reuses the same conversation context (`switch-demo`) so you
> can confirm the active provider by asking follow-up questions.

## Resetting The Proxy (Optional)

To wipe the LiteLLM state and rerun bootstrap:

```bash
docker compose down llm-proxy llm-proxy-db llm-proxy-bootstrap

docker volume rm fuzzforge_litellm_proxy_data fuzzforge_litellm_proxy_db

docker compose up -d llm-proxy-db llm-proxy
```

After the proxy is healthy, rerun the registration script and key update. The
bootstrap container mirrors secrets into `.env.litellm` and reissues the task
agent key automatically.

## How The Pieces Fit Together

1. **LiteLLM Proxy** exposes OpenAI-compatible routes and stores provider
   metadata in Postgres.
2. **Bootstrap Container** waits for `/health/liveliness`, mirrors secrets into
   `.env.litellm`, registers any models you script, and keeps the virtual key in
   sync with the discovered model list.
3. **Task Agent** calls the proxy via `FF_LLM_PROXY_BASE_URL`. The hot-swap tool
   updates the agent’s runtime configuration, so switching providers is just a
   control message.
4. **Virtual Keys** carry quotas and allowed models. Setting the `models` array
   to `[]` lets the key use anything registered on the proxy.

Keep the master key and generated virtual keys somewhere safe—they grant full
admin and agent access respectively. When you add a new provider (e.g., Ollama)
just register the model via `/model/new`, update the key if needed, and repeat
the hot-swap steps.
