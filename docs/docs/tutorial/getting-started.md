# Getting Started

This tutorial will guide you through setting up FuzzForge and running your first security workflow. By the end of this tutorial, you'll have FuzzForge running locally and will have executed a complete static analysis workflow on a test project.

## Prerequisites

Before we begin, ensure you have the following installed:

- **Docker Desktop** or **Docker Engine** (20.10.0 or later)
- **Docker Compose** (2.0.0 or later)
- **Python 3.11+** (for CLI installation)
- **Git** (for cloning the repository)
- **4GB+ RAM** available for workflow execution

## Step 1: Clone and Setup FuzzForge

First, let's clone the FuzzForge repository:

```bash
git clone https://github.com/FuzzingLabs/fuzzforge_ai.git
cd fuzzforge_ai
```

## Step 2: Configure Environment (Required)

**⚠️ This step is mandatory - Docker Compose will fail without it.**

Create the environment configuration file:

```bash
cp volumes/env/.env.example volumes/env/.env
```

This file is required for FuzzForge to start. You can leave it with default values if you're only using basic workflows.

### When you need to add API keys:

Edit `volumes/env/.env` and add your API keys if using:
- **AI-powered workflows**: `llm_secret_detection`
- **AI agent**: `ff ai agent`

Example:
```env
LITELLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-your-key-here
```

### Basic workflows that don't need API keys:
- `security_assessment`
- `gitleaks_detection`
- `trufflehog_detection`
- `atheris_fuzzing`
- `cargo_fuzzing`

## Step 3: Start FuzzForge

Start all FuzzForge services:

```bash
docker-compose -f docker-compose.yml up -d
```

This will start the FuzzForge platform with multiple services:

**Core Services:**
- **temporal**: Workflow orchestration server
- **temporal-ui**: Web UI for workflow monitoring (port 8080)
- **postgresql**: Database for Temporal state
- **minio**: S3-compatible storage for targets and results
- **minio-setup**: One-time MinIO bucket configuration (exits after setup)
- **backend**: FastAPI server and workflow management API
- **task-agent**: A2A agent coordination service

**Security Workers** (vertical toolchains):
- **worker-python**: Python security analysis and Atheris fuzzing
- **worker-rust**: Rust/Cargo fuzzing and native code analysis
- **worker-secrets**: Secret detection and credential scanning
- **worker-ossfuzz**: OSS-Fuzz integration (heavy development)
- **worker-android**: Android security analysis (early development)

Wait for all services to be healthy (this may take 2-3 minutes on first startup):

```bash
# Check service health
docker-compose -f docker-compose.yml ps

# Verify FuzzForge is ready
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

## Step 4: Install the CLI (Optional but Recommended)

Install the FuzzForge CLI for easier workflow management:

```bash
cd cli
pip install -e .
# or with uv:
uv tool install .
```

Verify CLI installation:

```bash
fuzzforge --version
```

Configure the CLI to connect to your local instance:

```bash
fuzzforge config set-server http://localhost:8000
```

## Step 5: Verify Available Workflows

List all available workflows to confirm the system is working:

```bash
# Using CLI
fuzzforge workflows list

# Using API
curl http://localhost:8000/workflows | jq .
```

You should see 6 production workflows:
- `static_analysis_scan`
- `secret_detection_scan`
- `infrastructure_scan`
- `penetration_testing_scan`
- `language_fuzzing`
- `security_assessment`

## Step 6: Run Your First Workflow

Let's run a security assessment workflow on one of the included vulnerable test projects.

### Using the CLI (Recommended):

```bash
# Navigate to a test project
cd /path/to/fuzzforge/test_projects/vulnerable_app

# Submit the workflow - CLI automatically uploads the local directory
fuzzforge workflow run security_assessment .

# The CLI will:
# 1. Detect that '.' is a local directory
# 2. Create a compressed tarball of the directory
# 3. Upload it to the backend via HTTP
# 4. The backend stores it in MinIO
# 5. The worker downloads it when ready to analyze

# Monitor the workflow
fuzzforge workflow status <run-id>

# View results when complete
fuzzforge finding <run-id>
```

### Using the API:

For local files, you can use the upload endpoint:

```bash
# Create tarball and upload
tar -czf project.tar.gz /path/to/your/project
curl -X POST "http://localhost:8000/workflows/security_assessment/upload-and-submit" \
     -F "file=@project.tar.gz"

# Check status
curl "http://localhost:8000/runs/{run-id}/status"

# Get findings
curl "http://localhost:8000/runs/{run-id}/findings"
```

**Note**: The CLI handles file upload automatically. For remote workflows where the target path exists on the backend server, you can still use path-based submission for backward compatibility.

## Step 7: Understanding the Results

The workflow will complete in 30-60 seconds and return results in SARIF format. For the test project, you should see:

- **Total findings**: 15-20 security issues
- **Tools used**: OpenGrep (Semgrep) and Bandit
- **Severity levels**: High, Medium, and Low vulnerabilities
- **Categories**: SQL injection, command injection, hardcoded secrets, etc.

Example output:
```json
{
  "workflow": "static_analysis_scan",
  "status": "completed",
  "total_findings": 18,
  "scan_status": {
    "opengrep": "success",
    "bandit": "success"
  },
  "severity_counts": {
    "high": 6,
    "medium": 5,
    "low": 7
  }
}
```

## Step 8: Access the Temporal Web UI

You can monitor workflow execution in real-time using the Temporal Web UI:

1. Open http://localhost:8080 in your browser
2. Navigate to "Workflows" to see workflow executions
3. Click on a workflow to see detailed execution history and activity results

You can also access the MinIO console to view uploaded targets:

1. Open http://localhost:9001 in your browser
2. Login with: `fuzzforge` / `fuzzforge123`
3. Browse the `targets` bucket to see uploaded files

## Next Steps

Congratulations! You've successfully:
- ✅ Installed and configured FuzzForge
- ✅ Configured Docker with the required insecure registry
- ✅ Started all FuzzForge services
- ✅ Run your first security workflow
- ✅ Retrieved and understood workflow results

### What to explore next:

1. **[Create Workflow Guide](../how-to/create-workflow.md)** - Create your own workflows !

### Common Issues:

If you encounter problems:

1. **Workflow crashes with registry errors**: Check Docker insecure registry configuration
2. **Services won't start**: Ensure ports 8000, 8233, 9000, 9001 are available
3. **No findings returned**: Verify the target path contains analyzable code files
4. **CLI not found**: Ensure Python/pip installation path is in your PATH
5. **Upload fails**: Check that MinIO is running and accessible at http://localhost:9000

See the [Troubleshooting Guide](../how-to/troubleshooting.md) for detailed solutions.

---

**🎉 You're now ready to use FuzzForge for security analysis!**

The next tutorial will teach you about the different types of workflows and when to use each one.
