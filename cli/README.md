# FuzzForge CLI

🛡️ **FuzzForge CLI** - Command-line interface for FuzzForge security testing platform

A comprehensive CLI for managing security testing workflows, monitoring runs in real-time, and analyzing findings with beautiful terminal interfaces and persistent project management.

## ✨ Features

- 📁 **Project Management** - Initialize and manage FuzzForge projects with local databases
- 🔧 **Workflow Management** - Browse, configure, and run security testing workflows
- 🚀 **Workflow Execution** - Execute and manage security testing workflows
- 🔍 **Findings Analysis** - View, export, and analyze security findings in multiple formats
- 📊 **Real-time Monitoring** - Live dashboards for fuzzing statistics and crash reports
- ⚙️ **Configuration** - Flexible project and global configuration management
- 🎨 **Rich UI** - Beautiful tables, progress bars, and interactive prompts
- 💾 **Persistent Storage** - SQLite database for runs, findings, and crash data
- 🛡️ **Error Handling** - Comprehensive error handling with user-friendly messages
- 🔄 **Network Resilience** - Automatic retries and graceful degradation

## 🚀 Quick Start

### Installation

#### Prerequisites
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager

#### Install FuzzForge CLI
```bash
# Clone the repository
git clone https://github.com/FuzzingLabs/fuzzforge_alpha.git
cd fuzzforge_alpha/cli

# Install globally with uv (recommended)
uv tool install .

# Alternative: Install in development mode
uv sync
uv add --editable ../sdk
uv tool install --editable .

# Verify installation
fuzzforge --help
```

#### Shell Completion (Optional)
```bash
# Install completion for your shell
fuzzforge --install-completion
```

### Initialize Your First Project

```bash
# Create a new project directory
mkdir my-security-project
cd my-security-project

# Initialize FuzzForge project
ff init

# Check status
fuzzforge status
```

This creates a `.fuzzforge/` directory with:
- SQLite database for persistent storage
- Configuration file (`config.yaml`)
- Project metadata

### Run Your First Analysis

```bash
# List available workflows
fuzzforge workflows list

# Get workflow details
fuzzforge workflows info security_assessment

# Submit a workflow for analysis
fuzzforge workflow security_assessment /path/to/your/code


# View findings when complete
fuzzforge finding <execution-id>
```

## 📚 Command Reference

### Project Management

#### `ff init`
Initialize a new FuzzForge project in the current directory.

```bash
ff init --name "My Security Project" --api-url "http://localhost:8000"
```

**Options:**
- `--name, -n` - Project name (defaults to directory name)
- `--api-url, -u` - FuzzForge API URL (defaults to http://localhost:8000)
- `--force, -f` - Force initialization even if project exists

#### `fuzzforge status`
Show comprehensive project and API status information.

```bash
fuzzforge status
```

Displays:
- Project information and configuration
- Database statistics (runs, findings, crashes)
- API connectivity and available workflows

### Workflow Management

#### `fuzzforge workflows list`
List all available security testing workflows.

```bash
fuzzforge workflows list
```

#### `fuzzforge workflows info <workflow-name>`
Show detailed information about a specific workflow.

```bash
fuzzforge workflows info security_assessment
```

Displays:
- Workflow metadata (version, author, description)
- Parameter schema and requirements
- Supported volume modes and features

#### `fuzzforge workflows parameters <workflow-name>`
Interactive parameter builder for workflows.

```bash
# Interactive mode
fuzzforge workflows parameters security_assessment

# Save parameters to file
fuzzforge workflows parameters security_assessment --output params.json

# Non-interactive mode (show schema only)
fuzzforge workflows parameters security_assessment --no-interactive
```

### Workflow Execution

#### `fuzzforge workflow <workflow> <target-path>`
Execute a security testing workflow.

```bash
# Basic execution
fuzzforge workflow security_assessment /path/to/code

# With parameters
fuzzforge workflow security_assessment /path/to/binary \
  --param timeout=3600 \
  --param iterations=10000

# With parameter file
fuzzforge workflow security_assessment /path/to/code \
  --param-file my-params.json

# Wait for completion
fuzzforge workflow security_assessment /path/to/code --wait
```

**Options:**
- `--param, -p` - Parameter in key=value format (can be used multiple times)
- `--param-file, -f` - JSON file containing parameters
- `--volume-mode, -v` - Volume mount mode: `ro` (read-only) or `rw` (read-write)
- `--timeout, -t` - Execution timeout in seconds
- `--interactive/--no-interactive, -i/-n` - Interactive parameter input
- `--wait, -w` - Wait for execution to complete

#### `fuzzforge workflow status [execution-id]`
Check the status of a workflow execution.

```bash
# Check specific execution
fuzzforge workflow status abc123def456

# Check most recent execution
fuzzforge workflow status
```

#### `fuzzforge workflow history`
Show workflow execution history from local database.

```bash
# List all executions
fuzzforge workflow history

# Filter by workflow
fuzzforge workflow history --workflow security_assessment

# Filter by status
fuzzforge workflow history --status completed

# Limit results
fuzzforge workflow history --limit 10
```

#### `fuzzforge workflow retry <execution-id>`
Retry a workflow with the same or modified parameters.

```bash
# Retry with same parameters
fuzzforge workflow retry abc123def456

# Modify parameters interactively
fuzzforge workflow retry abc123def456 --modify-params
```

### Findings Management

#### `fuzzforge finding [execution-id]`
View security findings for a specific execution.

```bash
# Display latest findings
fuzzforge finding

# Display specific execution findings
fuzzforge finding abc123def456
```

#### `fuzzforge findings`
Browse all security findings from local database.

```bash
# List all findings
fuzzforge findings

# Show findings history
fuzzforge findings history --limit 20
```

#### `fuzzforge finding export [execution-id]`
Export security findings in various formats.

```bash
# Export latest findings
fuzzforge finding export --format json

# Export specific execution findings
fuzzforge finding export abc123def456 --format sarif

# Export as CSV with output file
fuzzforge finding export abc123def456 --format csv --output report.csv

# Export as HTML report
fuzzforge finding export --format html --output report.html
```

### Configuration Management

#### `fuzzforge config show`
Display current configuration settings.

```bash
# Show project configuration
fuzzforge config show

# Show global configuration
fuzzforge config show --global
```

#### `fuzzforge config set <key> <value>`
Set a configuration value.

```bash
# Project settings
fuzzforge config set project.api_url "http://api.fuzzforge.com"
fuzzforge config set project.default_timeout 7200
fuzzforge config set project.default_workflow "security_assessment"

# Retention settings
fuzzforge config set retention.max_runs 200
fuzzforge config set retention.keep_findings_days 120

# Preferences
fuzzforge config set preferences.auto_save_findings true
fuzzforge config set preferences.show_progress_bars false

# Global configuration
fuzzforge config set project.api_url "http://global.api.com" --global
```

#### `fuzzforge config get <key>`
Get a specific configuration value.

```bash
fuzzforge config get project.api_url
fuzzforge config get retention.max_runs --global
```

#### `fuzzforge config reset`
Reset configuration to defaults.

```bash
# Reset project configuration
fuzzforge config reset

# Reset global configuration
fuzzforge config reset --global

# Skip confirmation
fuzzforge config reset --force
```

#### `fuzzforge config edit`
Open configuration file in default editor.

```bash
# Edit project configuration
fuzzforge config edit

# Edit global configuration
fuzzforge config edit --global
```

## 🏗️ Project Structure

When you initialize a FuzzForge project, the following structure is created:

```
my-project/
├── .fuzzforge/
│   ├── config.yaml          # Project configuration
│   └── findings.db          # SQLite database
├── .gitignore               # Updated with FuzzForge entries
└── README.md                # Project README (if created)
```

### Database Schema

The SQLite database stores:

- **runs** - Workflow run history and metadata
- **findings** - Security findings and SARIF data
- **crashes** - Crash reports and fuzzing data

### Configuration Format

Project configuration (`.fuzzforge/config.yaml`):

```yaml
project:
  name: "My Security Project"
  api_url: "http://localhost:8000"
  default_timeout: 3600
  default_workflow: null

retention:
  max_runs: 100
  keep_findings_days: 90

preferences:
  auto_save_findings: true
  show_progress_bars: true
  table_style: "rich"
  color_output: true
```

## 🔧 Advanced Usage

### Parameter Handling

FuzzForge CLI supports flexible parameter input:

1. **Command line parameters**:
   ```bash
   ff workflow workflow-name /path key1=value1 key2=value2
   ```

2. **Parameter files**:
   ```bash
   echo '{"timeout": 3600, "threads": 4}' > params.json
   ff workflow workflow-name /path --param-file params.json
   ```

3. **Interactive prompts**:
   ```bash
   ff workflow workflow-name /path --interactive
   ```

4. **Parameter builder**:
   ```bash
   ff workflows parameters workflow-name --output my-params.json
   ff workflow workflow-name /path --param-file my-params.json
   ```

### Environment Variables

Override configuration with environment variables:

```bash
export FUZZFORGE_API_URL="http://production.api.com"
export FUZZFORGE_TIMEOUT="7200"
```

### Data Retention

Configure automatic cleanup of old data:

```bash
# Keep only 50 runs
fuzzforge config set retention.max_runs 50

# Keep findings for 30 days
fuzzforge config set retention.keep_findings_days 30
```

### Export Formats

Support for multiple export formats:

- **JSON** - Simplified findings structure
- **CSV** - Tabular data for spreadsheets
- **HTML** - Interactive web report
- **SARIF** - Standard security analysis format

## 🛠️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/FuzzingLabs/fuzzforge_alpha.git
cd fuzzforge_alpha/cli

# Install in development mode
uv sync
uv add --editable ../sdk

# Install CLI in editable mode
uv tool install --editable .
```

### Project Structure

```
cli/
├── src/fuzzforge_cli/
│   ├── __init__.py
│   ├── main.py              # Main CLI app
│   ├── config.py            # Configuration management
│   ├── database.py          # Database operations
│   ├── exceptions.py        # Error handling
│   ├── api_validation.py    # API response validation
│   └── commands/            # Command implementations
│       ├── init.py          # Project initialization
│       ├── workflows.py     # Workflow management
│       ├── runs.py          # Run management
│       ├── findings.py      # Findings management
│       ├── config.py        # Configuration commands
│       └── status.py        # Status information
├── pyproject.toml           # Project configuration
└── README.md               # This file
```

### Running Tests

```bash
# Run tests (when available)
uv run pytest

# Code formatting
uv run black src/
uv run isort src/

# Type checking
uv run mypy src/
```

## ⚠️ Troubleshooting

### Common Issues

#### "No FuzzForge project found"
```bash
# Initialize a project first
ff init
```

#### API Connection Failed
```bash
# Check API URL configuration
fuzzforge config get project.api_url

# Test API connectivity
fuzzforge status

# Update API URL if needed
fuzzforge config set project.api_url "http://correct-url:8000"
```

#### Permission Errors
```bash
# Ensure proper permissions for project directory
chmod -R 755 .fuzzforge/

# Check file ownership
ls -la .fuzzforge/
```

#### Database Issues
```bash
# Check database file exists
ls -la .fuzzforge/findings.db

# Reinitialize if corrupted (will lose data)
rm .fuzzforge/findings.db
ff init --force
```

### Environment Variables

Set these environment variables for debugging:

```bash
export FUZZFORGE_DEBUG=1           # Enable debug logging
export FUZZFORGE_API_URL="..."     # Override API URL
export FUZZFORGE_TIMEOUT="30"      # Override timeout
```

### Getting Help

```bash
# General help
fuzzforge --help

# Command-specific help
ff workflows --help
ff workflow run --help

# Show version
fuzzforge --version
```

## 🏆 Example Workflow

Here's a complete example of analyzing a project:

```bash
# 1. Initialize project
mkdir my-security-audit
cd my-security-audit
ff init --name "Security Audit 2024"

# 2. Check available workflows
fuzzforge workflows list

# 3. Submit comprehensive security assessment
ff workflow security_assessment /path/to/source/code --wait

# 4. View findings in table format
fuzzforge findings get <run-id>

# 5. Export detailed report
fuzzforge findings export <run-id> --format html --output security_report.html

# 6. Check project statistics
fuzzforge status
```

## 📜 License

This project is licensed under the terms specified in the main FuzzForge repository.

## 🤝 Contributing

Contributions are welcome! Please see the main FuzzForge repository for contribution guidelines.

---

**FuzzForge CLI** - Making security testing workflows accessible and efficient from the command line.
