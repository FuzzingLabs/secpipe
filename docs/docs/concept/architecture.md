# Architecture

FuzzForge is a distributed, containerized platform for security analysis workflows. Its architecture is designed for scalability, isolation, and reliability, drawing on modern patterns like microservices and orchestration. This page explains the core architectural concepts behind FuzzForge, meaning what the main components are, how they interact, and why the system is structured this way.

:::warning

FuzzForge’s architecture is evolving. While the long-term goal is a hexagonal architecture, the current implementation is still in transition. Expect changes as the platform matures.

:::

---

## Why This Architecture?

FuzzForge’s architecture is shaped by several key goals:

- **Scalability:** Handle many workflows in parallel, scaling up or down as needed.
- **Isolation:** Run each workflow in its own secure environment, minimizing risk.
- **Reliability:** Ensure that failures in one part of the system don’t bring down the whole platform.
- **Extensibility:** Make it easy to add new workflows, tools, or integrations.

## High-Level System Overview

At a glance, FuzzForge is organized into several layers, each with a clear responsibility:

- **Client Layer:** Where users and external systems interact (CLI, API clients, MCP server).
- **API Layer:** The FastAPI backend, which exposes REST endpoints and manages requests.
- **Orchestration Layer:** Temporal server and vertical workers, which schedule and execute workflows.
- **Execution Layer:** Long-lived vertical worker containers with pre-installed toolchains, where workflows run.
- **Storage Layer:** PostgreSQL database, MinIO (S3-compatible storage), and worker cache for persistence.

Here’s a simplified view of how these layers fit together:

```mermaid
graph TB
    subgraph "Client Layer"
        CLI[CLI Client]
        API_Client[API Client]
        MCP[MCP Server]
    end

    subgraph "API Layer"
        FastAPI[FastAPI Backend]
        Router[Route Handlers]
        Middleware[Middleware Stack]
    end

    subgraph "Orchestration Layer"
        Temporal[Temporal Server]
        Workers[Vertical Workers]
        Scheduler[Workflow Scheduler]
    end

    subgraph "Execution Layer"
        Docker[Docker Engine]
        Containers[Workflow Containers]
        Registry[Docker Registry]
    end

    subgraph "Storage Layer"
        PostgreSQL[PostgreSQL Database]
        Volumes[Docker Volumes]
        Cache[Result Cache]
    end

    CLI --> FastAPI
    API_Client --> FastAPI
    MCP --> FastAPI

    FastAPI --> Router
    Router --> Middleware
    Middleware --> Temporal

    Temporal --> Workers
    Workers --> Scheduler
    Scheduler --> Docker

    Docker --> Containers
    Docker --> Registry
    Containers --> Volumes

    FastAPI --> PostgreSQL
    Workers --> PostgreSQL
    Containers --> Cache
```

## What Are the Main Components?

### API Layer

- **FastAPI Backend:** The main entry point for users and clients. Handles authentication, request validation, and exposes endpoints for workflow management, results, and health checks.
- **Middleware Stack:** Manages API keys, user authentication, CORS, logging, and error handling.

### Orchestration Layer

- **Temporal Server:** Schedules and tracks workflows, backed by PostgreSQL.
- **Vertical Workers:** Long-lived workers pre-built with domain-specific toolchains (Android, Rust, Web, etc.). Can be scaled horizontally.
- **Task Queues:** Route workflows to appropriate vertical workers based on workflow metadata.

### Execution Layer

- **Vertical Workers:** Long-lived processes with pre-installed security tools for specific domains.
- **MinIO Storage:** S3-compatible storage for uploaded targets and results.
- **Worker Cache:** Local cache for downloaded targets, with LRU eviction.

### Storage Layer

- **PostgreSQL Database:** Stores Temporal workflow state and metadata.
- **MinIO (S3):** Persistent storage for uploaded targets and workflow results.
- **Worker Cache:** Local filesystem cache for downloaded targets with workspace isolation:
  - **Isolated mode**: Each run gets `/cache/{target_id}/{run_id}/workspace/`
  - **Shared mode**: All runs share `/cache/{target_id}/workspace/`
  - **Copy-on-write mode**: Download once, copy per run
  - **LRU eviction** when cache exceeds configured size

## How Does Data Flow Through the System?

### Submitting a Workflow

1. **User submits a workflow** via CLI or API client (with optional file upload).
2. **If file provided, API uploads** to MinIO and gets a `target_id`.
3. **API validates** the request and submits to Temporal.
4. **Temporal routes** the workflow to the appropriate vertical worker queue.
5. **Worker downloads target** from MinIO to local cache (if needed).
6. **Worker executes workflow** with pre-installed tools.
7. **Results are stored** in MinIO and metadata in PostgreSQL.
8. **Status updates** flow back through Temporal and the API to the user.

```mermaid
sequenceDiagram
    participant User
    participant API
    participant MinIO
    participant Temporal
    participant Worker
    participant Cache

    User->>API: Submit workflow + file
    API->>API: Validate parameters
    API->>MinIO: Upload target file
    MinIO-->>API: Return target_id
    API->>Temporal: Submit workflow(target_id)
    Temporal->>Worker: Route to vertical queue
    Worker->>MinIO: Download target
    MinIO-->>Worker: Stream file
    Worker->>Cache: Store in local cache
    Worker->>Worker: Execute security tools
    Worker->>MinIO: Upload SARIF results
    Worker->>Temporal: Update status
    Temporal->>API: Workflow complete
    API->>User: Return results
```

### Retrieving Results

1. **User requests status or results** via the API.
2. **API queries the database** for workflow metadata.
3. **If complete,** results are fetched from storage and returned to the user.

## How Do Services Communicate?

- **Internally:** FastAPI talks to Temporal via gRPC; Temporal coordinates with workers over gRPC; workers access MinIO via S3 API. All core services use pooled connections to PostgreSQL.
- **Externally:** Users interact via CLI or API clients (HTTP REST).

## How Is Security Enforced?

- **Worker Isolation:** Each workflow runs in isolated vertical workers with pre-defined toolchains.
- **Storage Security:** Uploaded files stored in MinIO with lifecycle policies; read-only access by default.
- **API Security:** All endpoints validate inputs, enforce rate limits, and log requests for auditing.
- **No Host Access:** Workers access targets via MinIO, not host filesystem.

## How Does FuzzForge Scale?

- **Horizontally:** Add more vertical workers to handle more workflows in parallel. Scale specific worker types based on demand.
- **Vertically:** Adjust CPU and memory limits for workers and adjust concurrent activity limits.

Example Docker Compose scaling:
```yaml
services:
  worker-rust:
    deploy:
      replicas: 3  # Scale rust workers
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

## How Is It Deployed?

- **Development:** All services run via Docker Compose—backend, Temporal, vertical workers, database, and MinIO.
- **Production:** Add load balancers, Temporal clustering, database replication, and multiple worker instances for high availability. Health checks, metrics, and centralized logging support monitoring and troubleshooting.

## How Is Configuration Managed?

- **Environment Variables:** Control core settings like database URLs, MinIO endpoints, and Temporal addresses.
- **Service Discovery:** Docker Compose's internal DNS lets services find each other by name, with consistent port mapping and health check endpoints.

Example configuration:
```bash
COMPOSE_PROJECT_NAME=fuzzforge
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/fuzzforge
TEMPORAL_ADDRESS=temporal:7233
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=fuzzforge
S3_SECRET_KEY=fuzzforge123
```

## How Are Failures Handled?

- **Failure Isolation:** Each service is independent; failures don’t cascade. Circuit breakers and graceful degradation keep the system stable.
- **Recovery:** Automatic retries with backoff for transient errors, dead letter queues for persistent failures, and workflow state recovery after restarts.

## Implementation Details

- **Tech Stack:** FastAPI (Python async), Temporal, MinIO, Docker, Docker Compose, PostgreSQL (asyncpg), and boto3 (S3 client).
- **Performance:** Workflows start immediately (workers are long-lived); results are retrieved quickly thanks to MinIO caching and database indexing.
- **Extensibility:** Add new workflows by mounting code; add new vertical workers with specialized toolchains; extend the API with new endpoints.

---

## In Summary

FuzzForge’s architecture is designed to be robust, scalable, and secure—ready to handle demanding security analysis workflows in a modern, distributed environment. As the platform evolves, expect even more modularity and flexibility, making it easier to adapt to new requirements and technologies.
