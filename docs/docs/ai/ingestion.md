# Ingestion & Knowledge Graphs

The AI module keeps long-running context by mirroring your repository into a Cognee-powered knowledge graph and persisting conversations in local storage.

## CLI Commands

```bash
# Scan the current project (skips .git/, .fuzzforge/, virtualenvs, caches)
fuzzforge ingest --path . --recursive

# Alias - identical behaviour
fuzzforge rag ingest --path . --recursive
```

The command gathers files using the filters defined in `ai/src/fuzzforge_ai/ingest_utils.py`. By default it includes common source, configuration, and documentation file types while skipping temporary and dependency directories.

### Customising the File Set

Use CLI flags to override the defaults:

```bash
fuzzforge ingest --path backend --file-types .py --file-types .yaml --exclude node_modules --exclude dist
```

## Command Options

`fuzzforge ingest` exposes several flags (see `cli/src/fuzzforge_cli/commands/ingest.py`):

- `--recursive / -r` – Traverse sub-directories.
- `--file-types / -t` – Repeatable flag to whitelist extensions (`-t .py -t .rs`).
- `--exclude / -e` – Repeatable glob patterns to skip (`-e tests/**`).
- `--dataset / -d` – Write into a named dataset instead of `<project>_codebase`.
- `--force / -f` – Clear previous Cognee data before ingesting (prompts for confirmation unless flag supplied).

All runs automatically skip `.fuzzforge/**` and `.git/**` to avoid recursive ingestion of cache folders.

## Dataset Layout

- Primary dataset: `<project>_codebase`
- Additional datasets: create ad-hoc buckets such as `insights` via the `ingest_to_dataset` tool
- Storage location: `.fuzzforge/cognee/project_<id>/`

### Persistence Details

- Every dataset lives under `.fuzzforge/cognee/project_<id>/{data,system}`. These directories are safe to commit to long-lived storage (they only contain embeddings and metadata).
- Cognee assigns deterministic IDs per project; if you move the repository, copy the entire `.fuzzforge/cognee/` tree to retain graph history.
- `HybridMemoryManager` ensures answers from Cognee are written back into the ADK session store so future prompts can refer to the same nodes without repeating the query.
- All Cognee processing runs locally against the files you ingest. No external service calls are made unless you configure a remote Cognee endpoint.

## Prompt Examples

```
You> refresh the project knowledge graph for ./backend
Assistant> Kicks off `fuzzforge ingest` with recursive scan

You> search project knowledge for "temporal workflow" using INSIGHTS
Assistant> Routes to Cognee `search_project_knowledge`

You> ingest_to_dataset("Design doc for new scanner", "insights")
Assistant> Adds the provided text block to the `insights` dataset
```

## Environment Template

The CLI writes a template at `.fuzzforge/.env.template` when you initialise a project. Keep it in source control so collaborators can copy it to `.env` and fill in secrets.

```env
# Core LLM settings
LLM_PROVIDER=openai
LITELLM_MODEL=gpt-5-mini
OPENAI_API_KEY=sk-your-key

# FuzzForge backend (Temporal-powered)
FUZZFORGE_MCP_URL=http://localhost:8010/mcp

# Optional: knowledge graph provider
LLM_COGNEE_PROVIDER=openai
LLM_COGNEE_MODEL=gpt-5-mini
LLM_COGNEE_API_KEY=sk-your-key
```

Add comments or project-specific overrides as needed; the agent reads these variables on startup.

## Tips

- Re-run ingestion after significant code changes to keep the knowledge graph fresh.
- Large binary assets are skipped automatically—store summaries or documentation if you need them searchable.
- Set `FUZZFORGE_DEBUG=1` to surface verbose ingest logs during troubleshooting.
