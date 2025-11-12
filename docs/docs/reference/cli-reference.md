# FuzzForge CLI Reference

Complete reference for the FuzzForge CLI (`ff` command). Use this as your quick lookup for all commands, options, and examples.

---

## Global Options

| Option | Description |
|--------|-------------|
| `--help`, `-h` | Show help message |
| `--version`, `-v` | Show version information |

---

## Core Commands

### `ff init`

Initialize a new FuzzForge project in the current directory.

**Usage:**
```bash
ff init [OPTIONS]
```

**Options:**
- `--name`, `-n` — Project name (defaults to current directory name)
- `--api-url`, `-u` — FuzzForge API URL (defaults to http://localhost:8000)
- `--force`, `-f` — Force initialization even if project already exists

**Examples:**
```bash
ff init                           # Initialize with defaults
ff init --name my-project         # Set custom project name
ff init --api-url http://prod:8000  # Use custom API URL
```

---

### `ff status`

Show project and latest execution status.

**Usage:**
```bash
ff status
```

**Example Output:**
```
📊 Project Status
   Project: my-security-project
   API URL: http://localhost:8000

Latest Execution:
   Run ID: security_scan-a1b2c3
   Workflow: security_assessment
   Status: COMPLETED
   Started: 2 hours ago
```

---

### `ff config`

Manage project configuration.

**Usage:**
```bash
ff config                    # Show all config
ff config <key>              # Get specific value
ff config <key> <value>      # Set value
```

**Examples:**
```bash
ff config                         # Display all settings
ff config api_url                 # Get API URL
ff config api_url http://prod:8000  # Set API URL
```

---

### `ff clean`

Clean old execution data and findings.

**Usage:**
```bash
ff clean [OPTIONS]
```

**Options:**
- `--days`, `-d` — Remove data older than this many days (default: 90)
- `--dry-run` — Show what would be deleted without deleting

**Examples:**
```bash
ff clean                    # Clean data older than 90 days
ff clean --days 30          # Clean data older than 30 days
ff clean --dry-run          # Preview what would be deleted
```

---

## Workflow Commands

### `ff workflows`

Browse and list available workflows.

**Usage:**
```bash
ff workflows [COMMAND]
```

**Subcommands:**
- `list` — List all available workflows
- `info <workflow>` — Show detailed workflow information
- `params <workflow>` — Show workflow parameters

**Examples:**
```bash
ff workflows list                    # List all workflows
ff workflows info python_sast        # Show workflow details
ff workflows params python_sast      # Show parameters
```

---

### `ff workflow`

Execute and manage individual workflows.

**Usage:**
```bash
ff workflow <COMMAND>
```

**Subcommands:**

#### `ff workflow run`

Execute a security testing workflow.

**Usage:**
```bash
ff workflow run <workflow> <target> [params...] [OPTIONS]
```

**Arguments:**
- `<workflow>` — Workflow name
- `<target>` — Target path to analyze
- `[params...]` — Parameters as `key=value` pairs

**Options:**
- `--param-file`, `-f` — JSON file containing workflow parameters
- `--timeout`, `-t` — Execution timeout in seconds
- `--interactive` / `--no-interactive`, `-i` / `-n` — Interactive parameter input (default: interactive)
- `--wait`, `-w` — Wait for execution to complete
- `--live`, `-l` — Start live monitoring after execution
- `--auto-start` / `--no-auto-start` — Automatically start required worker
- `--auto-stop` / `--no-auto-stop` — Automatically stop worker after completion
- `--fail-on` — Fail build if findings match SARIF level (error, warning, note, info, all, none)
- `--export-sarif` — Export SARIF results to file after completion

**Examples:**
```bash
# Basic workflow execution
ff workflow run python_sast ./project

# With parameters
ff workflow run python_sast ./project check_secrets=true

# CI/CD integration - fail on errors
ff workflow run python_sast ./project --wait --no-interactive \
  --fail-on error --export-sarif results.sarif

# With parameter file
ff workflow run python_sast ./project --param-file config.json

# Live monitoring for fuzzing
ff workflow run atheris_fuzzing ./project --live
```

#### `ff workflow status`

Check status of latest or specific workflow execution.

**Usage:**
```bash
ff workflow status [run_id]
```

**Examples:**
```bash
ff workflow status                     # Show latest execution status
ff workflow status python_sast-abc123  # Show specific execution
```

#### `ff workflow history`

Show execution history.

**Usage:**
```bash
ff workflow history [OPTIONS]
```

**Options:**
- `--limit`, `-l` — Number of executions to show (default: 10)

**Example:**
```bash
ff workflow history --limit 20
```

#### `ff workflow retry`

Retry a failed workflow execution.

**Usage:**
```bash
ff workflow retry <run_id>
```

**Example:**
```bash
ff workflow retry python_sast-abc123
```

---

## Finding Commands

### `ff findings`

Browse all findings across executions.

**Usage:**
```bash
ff findings [COMMAND]
```

**Subcommands:**

#### `ff findings list`

List findings from a specific run.

**Usage:**
```bash
ff findings list [run_id] [OPTIONS]
```

**Options:**
- `--format` — Output format: table, json, sarif (default: table)
- `--save` — Save findings to file

**Examples:**
```bash
ff findings list                        # Show latest findings
ff findings list python_sast-abc123     # Show specific run
ff findings list --format json          # JSON output
ff findings list --format sarif --save  # Export SARIF
```

#### `ff findings export`

Export findings to various formats.

**Usage:**
```bash
ff findings export <run_id> [OPTIONS]
```

**Options:**
- `--format` — Output format: json, sarif, csv
- `--output`, `-o` — Output file path

**Example:**
```bash
ff findings export python_sast-abc123 --format sarif --output results.sarif
```

#### `ff findings history`

Show finding history across multiple runs.

**Usage:**
```bash
ff findings history [OPTIONS]
```

**Options:**
- `--limit`, `-l` — Number of runs to include (default: 10)

---

### `ff finding`

View and analyze individual findings.

**Usage:**
```bash
ff finding [id]                       # Show latest or specific finding
ff finding show <run_id> --id <id>    # Show specific finding detail
```

**Examples:**
```bash
ff finding                              # Show latest finding
ff finding python_sast-abc123           # Show specific run findings
ff finding show python_sast-abc123 --id f2cf5e3e  # Show specific finding
```

---

## Worker Management Commands

### `ff worker`

Manage Temporal workers for workflow execution.

**Usage:**
```bash
ff worker <COMMAND>
```

**Subcommands:**

#### `ff worker list`

List FuzzForge workers and their status.

**Usage:**
```bash
ff worker list [OPTIONS]
```

**Options:**
- `--all`, `-a` — Show all workers (including stopped)

**Examples:**
```bash
ff worker list          # Show running workers
ff worker list --all    # Show all workers
```

**Example Output:**
```
FuzzForge Workers
┏━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Worker  ┃ Status    ┃ Uptime         ┃
┡━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ android │ ● Running │ 5 minutes ago  │
│ python  │ ● Running │ 10 minutes ago │
└─────────┴───────────┴────────────────┘

✅ 2 worker(s) running
```

#### `ff worker start`

Start a specific worker.

**Usage:**
```bash
ff worker start <name> [OPTIONS]
```

**Arguments:**
- `<name>` — Worker name (e.g., python, android, rust, secrets)

**Options:**
- `--build` — Rebuild worker image before starting

**Examples:**
```bash
ff worker start python           # Start Python worker
ff worker start android --build  # Rebuild and start Android worker
```

**Available Workers:**
- `python` — Python security analysis and fuzzing
- `android` — Android APK analysis
- `rust` — Rust fuzzing and analysis
- `secrets` — Secret detection workflows
- `ossfuzz` — OSS-Fuzz integration

#### `ff worker stop`

Stop all running FuzzForge workers.

**Usage:**
```bash
ff worker stop [OPTIONS]
```

**Options:**
- `--all` — Stop all workers (default behavior, flag for clarity)

**Example:**
```bash
ff worker stop
```

**Note:** This command stops only worker containers, leaving core services (backend, temporal, minio) running.

---

## Monitoring Commands

### `ff monitor`

Real-time monitoring for running workflows.

**Usage:**
```bash
ff monitor [COMMAND]
```

**Subcommands:**
- `live <run_id>` — Live monitoring for a specific execution
- `stats <run_id>` — Show statistics for fuzzing workflows

**Examples:**
```bash
ff monitor live atheris-abc123    # Monitor fuzzing campaign
ff monitor stats atheris-abc123   # Show fuzzing statistics
```

---

## AI Integration Commands

### `ff ai`

AI-powered analysis and assistance.

**Usage:**
```bash
ff ai [COMMAND]
```

**Subcommands:**
- `agent` — Start interactive AI agent
- `status` — Check AI agent status
- `server [--port]` — Start AI agent server

**Planned Features (Coming Soon):**
- `analyze <run_id>` — Analyze findings with AI
- `explain <finding_id>` — Get AI explanation of a finding
- `remediate <finding_id>` — Get remediation suggestions

**Examples:**
```bash
ff ai agent                  # Start interactive AI agent
ff ai status                 # Check agent status
ff ai server --port 8080     # Start server on custom port
```

---

## Knowledge Ingestion Commands

### `ff ingest`

Ingest knowledge into the AI knowledge base.

**Usage:**
```bash
ff ingest [path] [OPTIONS]
```

**Options:**
- `--recursive, -r` — Recursively ingest directory contents
- `--file-types, -t` — Comma-separated file types to ingest (e.g., "md,txt,py")
- `--exclude, -e` — Patterns to exclude
- `--dataset, -d` — Target dataset name
- `--force, -f` — Force reingest even if already processed

**Examples:**
```bash
ff ingest ./docs/security.md                    # Ingest single file
ff ingest ./docs --recursive                    # Ingest directory recursively
ff ingest ./src -t "py,js" --exclude "test_*"  # Ingest with filters
ff ingest ./docs -d security_docs               # Ingest to specific dataset
```

---

## Common Workflow Examples

### CI/CD Integration

```bash
# Run security scan in CI, fail on errors
ff workflow run python_sast . \
  --wait \
  --no-interactive \
  --fail-on error \
  --export-sarif results.sarif
```

### Local Development

```bash
# Quick security check
ff workflow run python_sast ./my-code

# Check specific file types
ff workflow run python_sast . file_extensions='[".py",".js"]'

# Interactive parameter configuration
ff workflow run python_sast . --interactive
```

### Fuzzing Workflows

```bash
# Start fuzzing with live monitoring
ff workflow run atheris_fuzzing ./project --live

# Long-running fuzzing campaign
ff workflow run ossfuzz_campaign ./project \
  --auto-start \
  duration=3600 \
  --live
```

### Worker Management

```bash
# Check which workers are running
ff worker list

# Start needed worker manually
ff worker start python --build

# Stop all workers when done
ff worker stop
```

---

## Configuration Files

### Project Config (`.fuzzforge/config.json`)

```json
{
  "project_name": "my-security-project",
  "api_url": "http://localhost:8000",
  "default_workflow": "python_sast",
  "auto_start_workers": true,
  "auto_stop_workers": false
}
```

### Parameter File Example

```json
{
  "check_secrets": true,
  "file_extensions": [".py", ".js", ".go"],
  "severity_threshold": "medium",
  "exclude_patterns": ["**/test/**", "**/vendor/**"]
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Findings matched `--fail-on` criteria |
| 3 | Worker startup failed |
| 4 | Workflow execution failed |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FUZZFORGE_API_URL` | Backend API URL | http://localhost:8000 |
| `FUZZFORGE_ROOT` | FuzzForge installation directory | Auto-detected |
| `FUZZFORGE_DEBUG` | Enable debug logging | false |

---

## Tips and Best Practices

1. **Use `--no-interactive` in CI/CD** — Prevents prompts that would hang automated pipelines
2. **Use `--fail-on` for quality gates** — Fail builds based on finding severity
3. **Export SARIF for tool integration** — Most security tools support SARIF format
4. **Let workflows auto-start workers** — More efficient than manually managing workers
5. **Use `--wait` with `--export-sarif`** — Ensures results are available before export
6. **Check `ff worker list` regularly** — Helps manage system resources
7. **Use parameter files for complex configs** — Easier to version control and reuse

---

## Related Documentation

- [Docker Setup](../how-to/docker-setup.md) — Worker management and Docker configuration
- [Getting Started](../tutorial/getting-started.md) — Complete setup guide
- [Workflow Guide](../how-to/create-workflow.md) — Detailed workflow documentation
- [CI/CD Integration](../how-to/cicd-integration.md) — CI/CD setup examples

---

**Need Help?**

```bash
ff --help                # General help
ff workflow run --help   # Command-specific help
ff worker --help         # Worker management help
```
