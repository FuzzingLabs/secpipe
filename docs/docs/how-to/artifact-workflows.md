# How-To: Artifact Workflows in FuzzForge AI

Artifacts are the heart of FuzzForge AI’s collaborative workflows. They let you generate, share, analyze, and improve files—code, configs, reports, and more—across agents and projects. This guide shows you, step by step, how to use artifacts for practical, productive automation.

---

## 1. What is an Artifact?

An **artifact** is any file or structured content created, processed, or shared by FuzzForge AI or its agents. Artifacts can be:
- Generated code, configs, or documentation
- Analysis results or transformed data
- Files shared between agents (including user uploads)
- Anything you want to track, review, or improve

Artifacts are stored locally (in `.fuzzforge/artifacts/`) and can be served over HTTP for agent-to-agent workflows.

---

## 2. Creating Artifacts

### a. Natural Language Generation

Just ask FuzzForge to create something, and it will generate an artifact automatically.

**Examples:**
```bash
You> Create a Python script to analyze log files for errors
You> Generate a secure Docker configuration for a web application
You> Write a security checklist for code reviews
You> Create a CSV template for vulnerability tracking
```

**System Response:**
```
ARTIFACT: script log_analyzer.py
```
The file is now available in your artifact list!

---

### b. Sharing Files with Agents

Send any file (including artifacts) to a registered agent for further analysis or processing.

**Command Syntax:**
```bash
/sendfile <AgentName> <file_path_or_artifact_id> "<optional note>"
```

**Examples:**
```bash
/sendfile SecurityAnalyzer ./src/authentication.py "Please check for security vulnerabilities"
/sendfile ReverseEngineer ./suspicious.exe "Analyze this binary for malware"
/sendfile ConfigReviewer artifact_abc123 "Optimize this configuration"
```

**What happens:**
1. FuzzForge reads the file or artifact
2. Creates (or references) an artifact
3. Generates an HTTP URL for the artifact
4. Sends an A2A message to the target agent
5. The agent downloads and processes the file

---

### c. Analyzing and Improving Artifacts

After creating an artifact, you can request further analysis or improvements.

**Examples:**
```bash
You> Create a REST API security configuration
You> Send this configuration to SecurityAnalyzer for review
You> ROUTE_TO ConfigExpert: Analyze the configuration I just created
```

---

## 3. Viewing and Managing Artifacts

### a. List All Artifacts

```bash
/artifacts
```
Displays a table of all artifacts, including IDs, filenames, sizes, and creation times.

### b. View a Specific Artifact

```bash
/artifacts <artifact_id>
```
Shows details, download URL, and a content preview.

---

## 4. Advanced Artifact Workflows

### a. Generate-Analyze-Improve Cycle

```bash
# Step 1: Generate initial artifact
You> Create a secure API configuration for user authentication

# Step 2: Send to expert agent for analysis
You> /sendfile SecurityExpert artifact_abc123 "Review this config for security issues"

# Step 3: Request improvements based on feedback
You> Based on the security feedback, create an improved version of the API configuration
```

### b. Multi-Agent Artifact Processing

```bash
# Create initial content
You> Generate a Python web scraper for security data

# Send to different specialists
You> /sendfile CodeReviewer artifact_def456 "Check code quality and best practices"
You> /sendfile SecurityAnalyzer artifact_def456 "Analyze for security vulnerabilities"
You> /sendfile PerformanceExpert artifact_def456 "Optimize for performance"

# Consolidate feedback
You> Create an improved version incorporating all the expert feedback
```

### c. Artifact-Based Agent Coordination

```bash
You> Create a comprehensive security assessment report template

# System creates artifact_ghi789

You> ROUTE_TO DocumentExpert: Enhance this report template with professional formatting
You> ROUTE_TO SecurityManager: Add compliance sections to this report template
You> ROUTE_TO DataAnalyst: Add metrics and visualization sections to this template
```

---

## 5. Artifact Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/artifacts` | List all artifacts | `/artifacts` |
| `/artifacts <id>` | View artifact details | `/artifacts artifact_abc123` |
| `/sendfile <agent> <path/id> "<note>"` | Send file or artifact to agent | `/sendfile Analyzer ./code.py "Review this"` |

---

## 6. Where Are Artifacts Stored?

Artifacts are stored in your project’s `.fuzzforge/artifacts/` directory and are accessible via HTTP when the A2A server is running.

**Example structure:**
```
.fuzzforge/
└── artifacts/
    ├── artifact_abc123
    ├── artifact_def456
    └── artifact_ghi789
```

Each artifact gets a unique URL, e.g.:
```
http://localhost:10100/artifacts/artifact_abc123
```

---

## 7. Supported Artifact Types

| Type               | Extensions                | Example Requests                        |
|--------------------|--------------------------|-----------------------------------------|
| Python Scripts     | `.py`                     | "Create a script to..."                 |
| Configurations     | `.yaml`, `.json`, `.toml` | "Generate config for..."                |
| Documentation      | `.md`, `.txt`             | "Write documentation for..."            |
| SQL Queries        | `.sql`                    | "Write a query to..."                   |
| Shell Scripts      | `.sh`, `.bat`             | "Create a deployment script..."         |
| Web Files          | `.html`, `.css`, `.js`    | "Create a webpage..."                   |
| Data Files         | `.csv`, `.xml`            | "Create a data template..."             |

---

## 8. Tips & Best Practices

- Use clear, descriptive requests for artifact generation.
- Reference artifact IDs when sending files between agents for traceability.
- Combine artifact workflows with knowledge graph and memory features for maximum productivity.
- Artifacts are project-scoped—keep sensitive data within your project boundaries.

---

Artifacts make FuzzForge AI a powerful, collaborative automation platform. Experiment, share, and build smarter workflows—one artifact at a time!