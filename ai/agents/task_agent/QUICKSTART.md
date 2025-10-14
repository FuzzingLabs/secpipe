# Quick Start Guide

## Launch the Agent

From the repository root you can expose the agent through any ADK entry point:

```bash
# A2A / HTTP server
adk api_server --a2a --port 8000 agent_with_adk_format

# Browser UI
adk web agent_with_adk_format

# Interactive terminal
adk run agent_with_adk_format
```

The A2A server exposes the JSON-RPC endpoint at `http://localhost:8000/a2a/litellm_agent`.

## Hot-Swap from the Command Line

Use the bundled helper to change model and prompt via A2A without touching the UI:

```bash
python agent_with_adk_format/a2a_hot_swap.py \
  --model openai gpt-4o \
  --prompt "You are concise." \
  --config \
  --context demo-session
```

The script sends the control messages for you and prints the server’s responses. The `--context` flag lets you reuse the same conversation across multiple invocations.

### Follow-up Messages

Once the swaps are applied you can send a user message on the same session:

```bash
python agent_with_adk_format/a2a_hot_swap.py \
  --context demo-session \
  --message "Summarise the current configuration in five words."
```

### Clearing the Prompt

```bash
python agent_with_adk_format/a2a_hot_swap.py \
  --context demo-session \
  --prompt "" \
  --config
```

## Control Messages (for reference)

Behind the scenes the helper sends plain text messages understood by the callbacks:

- `[HOTSWAP:MODEL:provider/model]`
- `[HOTSWAP:PROMPT:text]`
- `[HOTSWAP:GET_CONFIG]`

You can craft the same messages from any A2A client if you prefer.
