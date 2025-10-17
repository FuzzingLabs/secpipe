# Prompt Patterns & Examples

Use the `fuzzforge ai agent` shell to mix structured slash commands with natural requests. The Google ADK runtime keeps conversation context, so follow-ups automatically reuse earlier answers, retrieved files, and workflow IDs.

## Slash Commands

| Command | Purpose | Example |
| --- | --- | --- |
| `/list` | Show registered A2A agents | `/list` |
| `/register <url>` | Register a remote agent card | `/register http://localhost:10201` |
| `/artifacts` | List generated artifacts with download links | `/artifacts` |
| `/sendfile <agent> <path> [note]` | Ship a file as an artifact to a remote peer | `/sendfile SecurityAnalyzer reports/latest.md "Please review"` |
| `/memory status` | Summarise conversational memory, session store, and Cognee directories | `/memory status` |
| `/memory datasets` | List available Cognee datasets | `/memory datasets` |
| `/recall <query>` | Search prior conversation context using semantic vectors | `/recall dependency updates` |

## Workflow Automation

```
You> list available fuzzforge workflows
Assistant> [returns workflow names, descriptions, and required parameters]

You> run fuzzforge workflow security_assessment on ./backend
Assistant> Submits the run, emits TaskStatusUpdateEvent entries, and links the SARIF artifact when complete.

You> show findings for that run once it finishes
Assistant> Streams the `get_comprehensive_scan_summary` output and attaches the artifact URI.
```

## Knowledge Graph & Memory Prompts

```
You> refresh the project knowledge graph for ./backend
Assistant> Launches `fuzzforge ingest --path ./backend --recursive` and reports file counts.

You> search project knowledge for "temporal readiness" using INSIGHTS
Assistant> Routes to Cognee via `query_project_knowledge_api` and returns the top matches.

You> recall "api key rotation"
Assistant> Uses the ADK semantic memory service to surface earlier chat snippets.
```

## Routing to Specialist Agents

```
You> ROUTE_TO SecurityAnalyzer: audit this Terraform module for secrets
Assistant> Delegates the request to `SecurityAnalyzer` using the A2A capability map.

You> sendfile DocumentationAgent docs/runbook.md "Incorporate latest workflow"
Assistant> Uploads the file as an artifact and notifies the remote agent.
```

## Prompt Tips

- Use explicit verbs (`list`, `run`, `search`) to trigger the Temporal workflow helpers.
- Include parameter names inline (`with target_branch=main`) so the executor maps values to MCP tool inputs without additional clarification.
- When referencing prior runs, reuse the assistant’s run IDs or ask for "the last run"—the session store tracks them per context ID.
- If Cognee is not configured, graph queries return a friendly notice; set `LLM_COGNEE_*` variables to enable full answers.
- Combine slash commands and natural prompts in the same session; the ADK session service keeps them in a single context thread.
- `/memory search <query>` is a shortcut for `/recall <query>` if you want status plus recall in one place.
