#!/bin/bash
set -e

# Wait for .env file to have keys (max 30 seconds)
echo "[task-agent] Waiting for virtual keys to be provisioned..."
for i in $(seq 1 30); do
    if [ -f /app/config/.env ]; then
        # Check if TASK_AGENT_API_KEY has a value (not empty)
        KEY=$(grep -E '^TASK_AGENT_API_KEY=' /app/config/.env | cut -d'=' -f2)
        if [ -n "$KEY" ] && [ "$KEY" != "" ]; then
            echo "[task-agent] Virtual keys found, loading environment..."
            # Export keys from .env file
            export TASK_AGENT_API_KEY="$KEY"
            export OPENAI_API_KEY=$(grep -E '^OPENAI_API_KEY=' /app/config/.env | cut -d'=' -f2)
            export FF_LLM_PROXY_BASE_URL=$(grep -E '^FF_LLM_PROXY_BASE_URL=' /app/config/.env | cut -d'=' -f2)
            echo "[task-agent] Loaded TASK_AGENT_API_KEY: ${TASK_AGENT_API_KEY:0:15}..."
            echo "[task-agent] Loaded FF_LLM_PROXY_BASE_URL: $FF_LLM_PROXY_BASE_URL"
            break
        fi
    fi
    echo "[task-agent] Keys not ready yet, waiting... ($i/30)"
    sleep 1
done

if [ -z "$TASK_AGENT_API_KEY" ]; then
    echo "[task-agent] ERROR: Virtual keys were not provisioned within 30 seconds!"
    exit 1
fi

echo "[task-agent] Starting uvicorn..."
exec "$@"
