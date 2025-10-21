---
title: "Run the LLM Proxy"
description: "Deploy Bifrost (default) or LiteLLM as an LLM gateway and connect it to the task agent."
---

## Overview

FuzzForge routes every LLM request through a proxy so that usage can be metered, priced, and rate limited per user. The repository now ships with Docker Compose profiles for two supported gateways:

- **Bifrost** (`maximhq/bifrost`) — default option with granular governance and budgeting
- **LiteLLM Proxy** (`ghcr.io/berriai/litellm`) — drop-in alternative that exposes similar OpenAI-compatible endpoints

Both services read provider credentials from `volumes/env/.env` and persist their internal state in dedicated Docker volumes, so configuration survives container restarts.

## Before You Start

1. Copy `volumes/env/.env.example` to `volumes/env/.env` and fill in:
   - Leave `OPENAI_API_KEY=sk-proxy-default`, or paste your raw OpenAI key if you
     want the bootstrapper to migrate it automatically into `volumes/env/.env.bifrost`
   - `FF_LLM_PROXY_BASE_URL` pointing to the proxy hostname inside Docker
   - Optional `LITELLM_MASTER_KEY`/`LITELLM_SALT_KEY` if you plan to run the LiteLLM proxy
2. When running tools outside Docker, change `FF_LLM_PROXY_BASE_URL` to the published host port (for example `http://localhost:10999`).

## Bifrost Gateway (default)

Start the service with the new Compose profile:

```bash
# Launch the proxy + UI (http://localhost:10999)
docker compose up llm-proxy
```

The container binds its SQLite databases underneath the named volume `fuzzforge_llm_proxy_data`, so your configuration, request logs, and issued virtual keys persist. On startup a bootstrap job seeds the default providers, creates the `fuzzforge-task-agent` virtual key, and writes the generated token back to `volumes/env/.env` so the agent picks it up automatically.

### Configure providers

1. Open `http://localhost:10999` and follow the onboarding flow.
2. Upstream keys are added automatically when the bootstrap job finds standard
   variables such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. The raw secrets
   are mirrored into `volumes/env/.env.bifrost`, so future restarts rehydrate the
   proxy without more manual edits. The same pass also generates `/app/data/config.json`
   (backed by the `fuzzforge_llm_proxy_data` volume) populated with provider entries,
   `client.drop_excess_requests=false`, and an enabled SQLite `config_store`, so
   budgets and UI-driven configuration persist exactly the way the docs expect.
   To raise the upstream timeout beyond the 30 s default, set `BIFROST_DEFAULT_TIMEOUT_SECONDS`
   or provider-specific overrides such as `BIFROST_ANTHROPIC_TIMEOUT_SECONDS` in
   `volumes/env/.env` before bootstrapping; the script propagates them to the proxy’s
   network configuration automatically.
3. (Optional) Set `BIFROST_OPENAI_MODELS` to a comma-separated list if you want
   to scope a key to specific models (for example `openai/gpt-5,openai/gpt-5-nano`).
   When you target Responses-only models, flip `BIFROST_OPENAI_USE_RESPONSES_API=true`
   so the proxy runs them against the newer endpoint. You can still add or rotate
   keys manually via **Providers → Add key**—reference either the migrated
   `env.BIFROST_*` variables or paste the secret directly.
4. (Optional) Add price caps, context window overrides, or caching policies from the same UI. Settings are stored immediately in the mounted data volume.

If you prefer a file-based bootstrap, mount a `config.json` under `/app/data` that references the same environment variables:

```json
{
  "providers": {
    "openai": {
      "keys": [{ "value": "env.BIFROST_OPENAI_KEY", "weight": 1.0 }]
    }
  }
}
```

### Issue per-user virtual keys

Virtual keys let you attach budgets and rate limits to each downstream agent. Create them from the UI (**Governance → Virtual Keys**) or via the API:

```bash
curl -X POST http://localhost:10999/api/governance/virtual-keys \
  -H "Authorization: Bearer <admin-access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "task-agent default",
    "user_id": "fuzzforge-task-agent",
    "budget": {"max_limit": 10.0, "reset_duration": "1d"}
  }'
```

Use the returned `key` value as the agent's `OPENAI_API_KEY`. When making requests manually, send the header `x-bf-vk: <virtual-key>` (the task agent handles this automatically once the key is in the environment).

You can generate scoped keys for teammates the same way to give each person isolated quotas and audit trails.

## LiteLLM Proxy (alternative)

If you prefer LiteLLM's gateway, enable the second profile:

```bash
# Requires LITELLM_MASTER_KEY + LITELLM_SALT_KEY in volumes/env/.env
docker compose --profile proxy-litellm up llm-proxy-litellm
```

The service exposes the admin UI at `http://localhost:4110/ui` and stores state in the `fuzzforge_litellm_proxy_data` volume (SQLite by default).

Generate user-facing keys with the built-in `/key/generate` endpoint:

```bash
curl http://localhost:4110/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "models": ["openai/gpt-4o-mini"],
    "metadata": {"user": "fuzzforge-task-agent"},
    "duration": "7d",
    "budget": {"soft": 8.0, "hard": 10.0}
  }'
```

Set the returned key as `OPENAI_API_KEY` for the task agent and update its base URL to `http://llm-proxy-litellm:4000` (or `http://localhost:4110` outside Docker).

## Wiring the Task Agent

Both proxies expose an OpenAI-compatible API. The LiteLLM agent only needs the base URL and a bearer token:

```bash
FF_LLM_PROXY_BASE_URL=http://llm-proxy:8080          # or http://llm-proxy-litellm:4000 when switching proxies
OPENAI_API_KEY=sk-proxy-default                      # virtual key issued by the gateway
LITELLM_MODEL=openai/gpt-5
LITELLM_PROVIDER=openai
```

The agent automatically forwards requests to the configured proxy and never touches the raw provider secrets. When you hot-swap models from the UI or CLI, the proxy enforces the budgets and rate limits tied to the virtual key.

To verify end‑to‑end connectivity, run:

```bash
curl -X POST http://localhost:10999/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-5",
    "messages": [{"role": "user", "content": "Proxy health check"}]
  }'
```

Replace the host/port with the LiteLLM endpoint when using that gateway.

## Switching Between Proxies

1. Stop the current proxy container.
2. Update `FF_LLM_PROXY_BASE_URL` in `volumes/env/.env` to the new service host (`llm-proxy` or `llm-proxy-litellm`).
3. Replace `OPENAI_API_KEY` with the virtual key generated by the selected proxy.
4. Restart the `task-agent` container so it picks up the new environment.

Because the agent only knows about the OpenAI-compatible interface, no further code changes are required when alternating between Bifrost and LiteLLM.
