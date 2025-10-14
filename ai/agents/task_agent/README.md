# LiteLLM Agent with Hot-Swap Support

A flexible AI agent powered by LiteLLM that supports runtime hot-swapping of models and system prompts. Compatible with ADK and A2A protocols.

## Features

- 🔄 **Hot-Swap Models**: Change LLM models on-the-fly without restarting
- 📝 **Dynamic Prompts**: Update system prompts during conversation
- 🌐 **Multi-Provider Support**: Works with OpenAI, Anthropic, Google, OpenRouter, and more
- 🔌 **A2A Compatible**: Can be served as an A2A agent
- 🛠️ **ADK Integration**: Run with `adk web`, `adk run`, or `adk api_server`

## Architecture

```
task_agent/
├── __init__.py              # Exposes root_agent for ADK
├── a2a_hot_swap.py          # JSON-RPC helper for hot-swapping
├── README.md                # This guide
├── QUICKSTART.md            # Quick-start walkthrough
├── .env                     # Active environment (gitignored)
├── .env.example             # Environment template
└── litellm_agent/
    ├── __init__.py
    ├── agent.py             # Main agent implementation
    ├── agent.json           # A2A agent card
    ├── callbacks.py         # ADK callbacks
    ├── config.py            # Defaults and state keys
    ├── control.py           # HOTSWAP message helpers
    ├── prompts.py           # Base instruction
    ├── state.py             # Session state utilities
    └── tools.py             # set_model / set_prompt / get_config
```

## Setup

### 1. Environment Configuration

Copying the example file is optional—the repository already ships with a root-level `.env` seeded with defaults. Adjust the values at the package root:
```bash
cd task_agent
# Optionally refresh from the template
# cp .env.example .env
```

Edit `.env` (or `.env.example`) and add your API keys. The agent must be restarted after changes so the values are picked up:
```bash
# Set default model
LITELLM_MODEL=gemini/gemini-2.0-flash-001

# Add API keys for providers you want to use
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 2. Install Dependencies

```bash
pip install "google-adk" "a2a-sdk[all]" "python-dotenv" "litellm"
```

### 3. Run in Docker

Build the container (this image can be pushed to any registry or run locally):

```bash
docker build -t litellm-hot-swap:latest task_agent
```

Provide environment configuration at runtime (either pass variables individually or mount a file):

```bash
docker run \
  -p 8000:8000 \
  --env-file task_agent/.env \
  litellm-hot-swap:latest
```

The container starts Uvicorn with the ADK app (`main.py`) listening on port 8000.

## Running the Agent

### Option 1: ADK Web UI (Recommended for Testing)

Start the web interface:
```bash
adk web task_agent
```

> **Tip:** before launching `adk web`/`adk run`/`adk api_server`, ensure the root-level `.env` contains valid API keys for any provider you plan to hot-swap to (e.g. set `OPENAI_API_KEY` before switching to `openai/gpt-4o`).

Open http://localhost:8000 in your browser and interact with the agent.

### Option 2: ADK Terminal

Run in terminal mode:
```bash
adk run task_agent
```

### Option 3: A2A API Server

Start as an A2A-compatible API server:
```bash
adk api_server --a2a --port 8000 task_agent
```

The agent will be available at: `http://localhost:8000/a2a/litellm_agent`

### Command-line helper

Use the bundled script to drive hot-swaps and user messages over A2A:

```bash
python task_agent/a2a_hot_swap.py \
  --url http://127.0.0.1:8000/a2a/litellm_agent \
  --model openai gpt-4o \
  --prompt "You are concise." \
  --config \
  --context demo-session
```

To send a follow-up prompt in the same session (with a larger timeout for long answers):

```bash
python task_agent/a2a_hot_swap.py \
  --url http://127.0.0.1:8000/a2a/litellm_agent \
  --model openai gpt-4o \
  --prompt "You are concise." \
  --message "Give me a fuzzing harness." \
  --context demo-session \
  --timeout 120
```

> Ensure the corresponding provider keys are present in `.env` (or passed via environment variables) before issuing model swaps.

## Hot-Swap Tools

The agent provides three special tools:

### 1. `set_model` - Change the LLM Model

Change the model during conversation:

```
User: Use the set_model tool to change to gpt-4o with openai provider
Agent: ✅ Model configured to: openai/gpt-4o
       This change is active now!
```

**Parameters:**
- `model`: Model name (e.g., "gpt-4o", "claude-3-sonnet-20240229")
- `custom_llm_provider`: Optional provider prefix (e.g., "openai", "anthropic", "openrouter")

**Examples:**
- OpenAI: `set_model(model="gpt-4o", custom_llm_provider="openai")`
- Anthropic: `set_model(model="claude-3-sonnet-20240229", custom_llm_provider="anthropic")`
- Google: `set_model(model="gemini-2.0-flash-001", custom_llm_provider="gemini")`

### 2. `set_prompt` - Change System Prompt

Update the system instructions:

```
User: Use set_prompt to change my behavior to "You are a helpful coding assistant"
Agent: ✅ System prompt updated:
       You are a helpful coding assistant

       This change is active now!
```

### 3. `get_config` - View Configuration

Check current model and prompt:

```
User: Use get_config to show me your configuration
Agent: 📊 Current Configuration:
       ━━━━━━━━━━━━━━━━━━━━━━
       Model: openai/gpt-4o
       System Prompt: You are a helpful coding assistant
       ━━━━━━━━━━━━━━━━━━━━━━
```

## Testing

### Basic A2A Client Test

```bash
python agent/test_a2a_client.py
```

### Hot-Swap Functionality Test

```bash
python agent/test_hotswap.py
```

This will:
1. Check initial configuration
2. Query with default model
3. Hot-swap to GPT-4o
4. Verify model changed
5. Change system prompt
6. Test new prompt behavior
7. Hot-swap to Claude
8. Verify final configuration

### Command-Line Hot-Swap Helper

You can trigger model and prompt changes directly against the A2A endpoint without the interactive CLI:

```bash
# Start the agent first (in another terminal):
adk api_server --a2a --port 8000 task_agent

# Apply swaps via pure A2A calls
python task_agent/a2a_hot_swap.py --model openai gpt-4o --prompt "You are concise." --config
python task_agent/a2a_hot_swap.py --model anthropic claude-3-sonnet-20240229 --context shared-session --config
python task_agent/a2a_hot_swap.py --prompt "" --context shared-session --config  # Clear the prompt and show current state
```

`--model` accepts either `provider/model` or a provider/model pair. Add `--context` if you want to reuse the same conversation across invocations. Use `--config` to dump the agent's configuration after the changes are applied.

## Supported Models

### OpenAI
- `openai/gpt-4o`
- `openai/gpt-4-turbo`
- `openai/gpt-3.5-turbo`

### Anthropic
- `anthropic/claude-3-opus-20240229`
- `anthropic/claude-3-sonnet-20240229`
- `anthropic/claude-3-haiku-20240307`

### Google
- `gemini/gemini-2.0-flash-001`
- `gemini/gemini-2.5-pro-exp-03-25`
- `vertex_ai/gemini-2.0-flash-001`

### OpenRouter
- `openrouter/anthropic/claude-3-opus`
- `openrouter/openai/gpt-4`
- Any model from OpenRouter catalog

## How It Works

### Session State
- Model and prompt settings are stored in session state
- Each session maintains its own configuration
- Settings persist across messages in the same session

### Hot-Swap Mechanism
1. Tools update session state with new model/prompt
2. `before_agent_callback` checks for changes
3. If model changed, directly updates: `agent.model = LiteLlm(model=new_model)`
4. Dynamic instruction function reads custom prompt from session state

### A2A Compatibility
- Agent card at `agent.json` defines A2A metadata
- Served at `/a2a/litellm_agent` endpoint
- Compatible with A2A client protocol

## Example Usage

### Interactive Session

```python
from a2a.client import A2AClient
import asyncio

async def chat():
    client = A2AClient("http://localhost:8000/a2a/litellm_agent")
    context_id = "my-session-123"

    # Start with default model
    async for msg in client.send_message("Hello!", context_id=context_id):
        print(msg)

    # Switch to GPT-4
    async for msg in client.send_message(
        "Use set_model with model gpt-4o and provider openai",
        context_id=context_id
    ):
        print(msg)

    # Continue with new model
    async for msg in client.send_message(
        "Help me write a function",
        context_id=context_id
    ):
        print(msg)

asyncio.run(chat())
```

## Troubleshooting

### Model Not Found
- Ensure API key for the provider is set in `.env`
- Check model name is correct for the provider
- Verify LiteLLM supports the model (https://docs.litellm.ai/docs/providers)

### Connection Refused
- Ensure the agent is running (`adk api_server --a2a task_agent`)
- Check the port matches (default: 8000)
- Verify no firewall blocking localhost

### Hot-Swap Not Working
- Check that you're using the same `context_id` across messages
- Ensure the tool is being called (not just asked to switch)
- Look for `🔄 Hot-swapped model to:` in server logs

## Development

### Adding New Tools

```python
async def my_tool(tool_ctx: ToolContext, param: str) -> str:
    """Your tool description."""
    # Access session state
    tool_ctx.state["my_key"] = "my_value"
    return "Tool result"

# Add to agent
root_agent = LlmAgent(
    # ...
    tools=[set_model, set_prompt, get_config, my_tool],
)
```

### Modifying Callbacks

```python
async def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """Modify response after model generates it."""
    # Your logic here
    return llm_response
```

## License

Apache 2.0
