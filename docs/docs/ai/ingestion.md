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
- Storage location (service default): `s3://<bucket>/<prefix>/project_<id>/{data,system}` as defined by the Cognee service (the docker compose stack seeds a `cognee` bucket automatically).
- Local mode (opt-in): set `COGNEE_STORAGE_BACKEND=local` to fall back to `.fuzzforge/cognee/project_<id>/` when developing without MinIO.

### Persistence Details

- The Cognee service keeps datasets inside the configured bucket/prefix (`s3://<bucket>/<prefix>/project_<id>/{data,system}`) so every project has its own Ladybug + LanceDB pair. Local mode mirrors the same layout under `.fuzzforge/cognee/project_<id>/`.
- Cognee assigns deterministic IDs per project; copy the entire prefix (local or S3) if you migrate repositories to retain graph history.
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
COGNEE_SERVICE_URL=http://localhost:18000
COGNEE_API_KEY=
```

The CLI auto-registers a dedicated Cognee account per project the first time you ingest (email pattern `project_<id>@cognee.local`). Set `COGNEE_SERVICE_EMAIL` / `COGNEE_SERVICE_PASSWORD` in `.fuzzforge/.env` if you prefer to reuse an existing login.

Switch the knowledge graph storage to S3/MinIO by adding:

```env
COGNEE_STORAGE_BACKEND=s3
COGNEE_S3_BUCKET=cognee
COGNEE_S3_PREFIX=project_${PROJECT_ID}
COGNEE_S3_ENDPOINT=http://localhost:9000
COGNEE_S3_ACCESS_KEY=fuzzforge
COGNEE_S3_SECRET_KEY=fuzzforge123
COGNEE_S3_ALLOW_HTTP=1
```

The default `docker-compose` stack already seeds a `cognee` bucket inside MinIO so these values work out-of-the-box. Point `COGNEE_SERVICE_URL` at the Cognee container (included in `docker/docker-compose.cognee.yml`) so `fuzzforge ingest` sends all requests to the shared service instead of importing Cognee locally.

Add comments or project-specific overrides as needed; the agent reads these variables on startup.

## Event-Driven Ingestion

Uploading files directly into MinIO triggers Cognee automatically. The dispatcher watches `s3://cognee/projects/<project-id>/...` and translates the top-level folder into a dataset:

| Prefix     | Dataset name                          |
|-----------|---------------------------------------|
| `files/`  | `<project-id>_codebase`                |
| `findings/` | `<project-id>_findings`             |
| `docs/`   | `<project-id>_docs`                    |

Under the hood MinIO publishes a `PUT` event → RabbitMQ (`cognee-ingest` exchange) → the `ingestion-dispatcher` container downloads the object and calls `/api/v1/add` + `/api/v1/cognify` using the deterministic project credentials (`project_<id>@fuzzforge.dev`). That means rsync, `aws s3 cp`, GitHub Actions, or any other tool that writes to the bucket can seed Cognee without touching the CLI.

## Tips

- Re-run ingestion after significant code changes to keep the knowledge graph fresh.
- Large binary assets are skipped automatically—store summaries or documentation if you need them searchable.
- Set `FUZZFORGE_DEBUG=1` to surface verbose ingest logs during troubleshooting.
