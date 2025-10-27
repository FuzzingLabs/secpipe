---
title: "Run the LLM Proxy"
description: "Run the LiteLLM gateway that ships with FuzzForge and connect it to the task agent."
---

## Overview

FuzzForge routes every LLM request through a LiteLLM proxy so that usage can be
metered, priced, and rate limited per user. Docker Compose starts the proxy in a
hardened container, while a bootstrap job seeds upstream provider secrets and
issues a virtual key for the task agent automatically.

LiteLLM exposes the OpenAI-compatible APIs (`/v1/*`) plus a rich admin UI. All
traffic stays on your network and upstream credentials never leave the proxy
container.

## Before You Start

1. Copy `volumes/env/.env.template` to `volumes/env/.env` and set the basics:
   - `LITELLM_MASTER_KEY` — admin token used to manage the proxy
   - `LITELLM_SALT_KEY` — random string used to encrypt provider credentials
   - Provider secrets under `LITELLM_<PROVIDER>_API_KEY` (for example
     `LITELLM_OPENAI_API_KEY`)
   - Leave `OPENAI_API_KEY=sk-proxy-default`; the bootstrap job replaces it with a
     LiteLLM-issued virtual key
2. When running tools outside Docker, change `FF_LLM_PROXY_BASE_URL` to the
   published host port (`http://localhost:10999`). Inside Docker the default
   value `http://llm-proxy:4000` already resolves to the container.

## Start the Proxy

```bash
docker compose up llm-proxy
```

The service publishes two things:

- HTTP API + admin UI on `http://localhost:10999`
- Persistent SQLite state inside the named volume
  `fuzzforge_litellm_proxy_data`

The UI login uses the `UI_USERNAME` / `UI_PASSWORD` pair (defaults to
`fuzzforge` / `fuzzforge123`). To change them, set the environment variables
before you run `docker compose up`:

```bash
export UI_USERNAME=myadmin
export UI_PASSWORD=super-secret
docker compose up llm-proxy
```

You can also edit the values directly in `docker-compose.yml` if you prefer to
check them into a different secrets manager.

Proxy-wide settings now live in `volumes/litellm/proxy_config.yaml`. By
default it enables `store_model_in_db` and `store_prompts_in_spend_logs`, which
lets the UI display request/response payloads for new calls. Update this file
if you need additional LiteLLM options and restart the `llm-proxy` container.

LiteLLM's health endpoint lives at `/health/liveliness`. You can verify it from
another terminal:

```bash
curl http://localhost:10999/health/liveliness
```

## What the Bootstrapper Does

During startup the `llm-proxy-bootstrap` container performs three actions:

1. **Wait for the proxy** — Blocks until `/health/liveliness` becomes healthy.
2. **Mirror provider secrets** — Reads `volumes/env/.env` and writes any
   `LITELLM_*_API_KEY` values into `volumes/env/.env.litellm`. The file is
   created automatically on first boot; if you delete it, bootstrap will
   recreate it and the proxy continues to read secrets from `.env`.
3. **Issue the default virtual key** — Calls `/key/generate` with the master key
   and persists the generated token back into `volumes/env/.env` (replacing the
   `sk-proxy-default` placeholder). The key is scoped to
   `LITELLM_DEFAULT_MODELS` when that variable is set; otherwise it uses the
   model from `LITELLM_MODEL`.

The sequence is idempotent. Existing provider secrets and virtual keys are
reused on subsequent runs, and the allowed-model list is refreshed via
`/key/update` if you change the defaults.

## Managing Virtual Keys

LiteLLM keys act as per-user credentials. The default key, named
`task-agent default`, is created automatically for the task agent. You can issue
more keys for teammates or CI jobs with the same management API:

```bash
curl http://localhost:10999/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "demo-user",
    "user_id": "demo",
    "models": ["openai/gpt-4o-mini"],
    "duration": "30d",
    "max_budget": 50,
    "metadata": {"team": "sandbox"}
  }'
```

Use `/key/update` to adjust budgets or the allowed-model list on existing keys:

```bash
curl http://localhost:10999/key/update \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "sk-...",            
    "models": ["openai/*", "anthropic/*"],
    "max_budget": 100
  }'
```

The admin UI (navigate to `http://localhost:10999/ui`) provides equivalent
controls for creating keys, routing models, auditing spend, and exporting logs.

## Wiring the Task Agent

The task agent already expects to talk to the proxy. Confirm these values in
`volumes/env/.env` before launching the stack:

```bash
FF_LLM_PROXY_BASE_URL=http://llm-proxy:4000          # or http://localhost:10999 when outside Docker
OPENAI_API_KEY=<virtual key created by bootstrap>
LITELLM_MODEL=openai/gpt-5
LITELLM_PROVIDER=openai
```

Restart the agent container after changing environment variables so the process
picks up the updates.

To validate the integration end to end, call the proxy directly:

```bash
curl -X POST http://localhost:10999/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Proxy health check"}]
  }'
```

A JSON response indicates the proxy can reach your upstream provider using the
mirrored secrets.

## Local Runtimes (Ollama, etc.)

LiteLLM supports non-hosted providers as well. To route requests to a local
runtime such as Ollama:

1. Set the appropriate provider key in the env file
   (for Ollama, point LiteLLM at `OLLAMA_API_BASE` inside the container).
2. Add the passthrough model either from the UI (**Models → Add Model**) or
   by calling `/model/new` with the master key.
3. Update `LITELLM_DEFAULT_MODELS` (and regenerate the virtual key if you want
the default key to include it).

The task agent keeps using the same OpenAI-compatible surface while LiteLLM
handles the translation to your runtime.

## Next Steps

- Explore [LiteLLM's documentation](https://docs.litellm.ai/docs/simple_proxy)
  for advanced routing, cost controls, and observability hooks.
- Configure Slack/Prometheus integrations from the UI to monitor usage.
- Rotate the master key periodically and store it in your secrets manager, as it
  grants full admin access to the proxy.

## Observability

LiteLLM ships with OpenTelemetry hooks for traces and metrics. This repository
already includes an OTLP collector (`otel-collector` service) and mounts a
default configuration that forwards traces to standard output. To wire it up:

1. Edit `volumes/otel/collector-config.yaml` if you want to forward to Jaeger,
   Datadog, etc. The initial config uses the logging exporter so you can see
   spans immediately via `docker compose logs -f otel-collector`.
2. Customize `volumes/litellm/proxy_config.yaml` if you need additional
   callbacks; `general_settings.otel: true` and `litellm_settings.callbacks:
   ["otel"]` are already present so no extra code changes are required.
3. (Optional) Override `OTEL_EXPORTER_OTLP_*` environment variables in
   `docker-compose.yml` or your shell to point at a remote collector.

After updating the configs, run `docker compose up -d otel-collector llm-proxy`
and generate a request (for example, trigger `ff workflow run llm_analysis`).
New traces will show up in the collector logs or whichever backend you
configured. See the official LiteLLM guide for advanced exporter options:
https://docs.litellm.ai/docs/observability/opentelemetry_integration.
