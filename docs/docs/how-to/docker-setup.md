# Docker Requirements for FuzzForge

FuzzForge runs entirely in Docker containers with Temporal orchestration. This guide covers system requirements, worker profiles, and resource management to help you run FuzzForge efficiently.

---

## System Requirements

### Docker Version

- **Docker Engine**: 20.10.0 or later
- **Docker Compose**: 2.0.0 or later

Verify your installation:

```bash
docker --version
docker compose version
```

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB+ |
| Disk | 20 GB free | 50 GB+ free |
| Network | Internet access | Stable connection |

### Port Requirements

FuzzForge services use these ports (must be available):

| Port | Service | Purpose |
|------|---------|---------|
| 8000 | Backend API | FastAPI server |
| 8080 | Temporal UI | Workflow monitoring |
| 7233 | Temporal gRPC | Workflow execution |
| 9000 | MinIO API | S3-compatible storage |
| 9001 | MinIO Console | Storage management |
| 5432 | PostgreSQL | Temporal database |

Check for port conflicts:

```bash
# macOS/Linux
lsof -i :8000,8080,7233,9000,9001,5432

# Or just try starting FuzzForge
docker compose -f docker-compose.yml up -d
```

---

## Worker Profiles (Resource Optimization)

FuzzForge uses Docker Compose **profiles** to prevent workers from auto-starting. This saves 5-7GB of RAM by only running workers when needed.

### Profile Configuration

Workers are configured with profiles in `docker-compose.yml`:

```yaml
worker-ossfuzz:
  profiles:
    - workers    # For starting all workers
    - ossfuzz    # For starting just this worker
  restart: "no"  # Don't auto-restart

worker-python:
  profiles:
    - workers
    - python
  restart: "no"

worker-rust:
  profiles:
    - workers
    - rust
  restart: "no"
```

### Default Behavior

**`docker compose up -d`** starts only core services:
- temporal
- temporal-ui
- postgresql
- minio
- minio-setup
- backend
- task-agent

Workers remain stopped until needed.

### On-Demand Worker Startup

When you run a workflow via the CLI, FuzzForge automatically starts the required worker:

```bash
# Automatically starts worker-python
fuzzforge workflow run atheris_fuzzing ./project

# Automatically starts worker-rust
fuzzforge workflow run cargo_fuzzing ./rust-project

# Automatically starts worker-secrets
fuzzforge workflow run secret_detection ./codebase
```

### Manual Worker Management

Start specific workers when needed:

```bash
# Start a single worker
docker start fuzzforge-worker-python

# Start all workers at once (uses more RAM)
docker compose --profile workers up -d

# Stop a worker to free resources
docker stop fuzzforge-worker-ossfuzz
```

### Resource Comparison

| Command | Workers Started | RAM Usage |
|---------|----------------|-----------|
| `docker compose up -d` | None (core only) | ~1.2 GB |
| `fuzzforge workflow run atheris_fuzzing .` | Python worker only | ~2-3 GB |
| `fuzzforge workflow run ossfuzz_campaign .` | OSS-Fuzz worker only | ~3-5 GB |
| `docker compose --profile workers up -d` | All workers | ~8 GB |

---

## Storage Management

### Docker Volume Cleanup

FuzzForge creates Docker volumes for persistent data. Clean them up periodically:

```bash
# Remove unused volumes (safe - keeps volumes for running containers)
docker volume prune

# List FuzzForge volumes
docker volume ls | grep fuzzforge

# Remove specific volume (WARNING: deletes data)
docker volume rm fuzzforge_minio-data
```

### Cache Directory

Workers use `/cache` inside containers for downloaded targets. This is managed automatically with LRU eviction, but you can check usage:

```bash
# Check cache usage in a worker
docker exec fuzzforge-worker-python du -sh /cache

# Clear cache manually if needed (safe - will re-download targets)
docker exec fuzzforge-worker-python rm -rf /cache/*
```

---

## Environment Configuration

FuzzForge requires `volumes/env/.env` to start. This file contains API keys and configuration:

```bash
# Copy the example file
cp volumes/env/.env.example volumes/env/.env

# Edit to add your API keys (if using AI features)
nano volumes/env/.env
```

See [Getting Started](../tutorial/getting-started.md) for detailed environment setup.

---

## Troubleshooting

### Services Won't Start

**Check ports are available:**
```bash
docker compose -f docker-compose.yml ps
lsof -i :8000,8080,7233,9000,9001
```

**Check Docker resources:**
```bash
docker system df
docker system prune  # Free up space if needed
```

### Worker Memory Issues

If workers crash with OOM (out of memory) errors:

1. **Close other applications** to free RAM
2. **Start only needed workers** (don't use `--profile workers`)
3. **Increase Docker Desktop memory limit** (Settings → Resources)
4. **Monitor usage**: `docker stats`

### Slow Worker Startup

Workers pull large images (~2-5GB each) on first run:

```bash
# Check download progress
docker compose logs worker-python -f

# Pre-pull images (optional)
docker compose pull
```

---

## Best Practices

1. **Default startup**: Use `docker compose up -d` (core services only)
2. **Let CLI manage workers**: Workers start automatically when workflows run
3. **Stop unused workers**: Free RAM when not running workflows
4. **Monitor resources**: `docker stats` shows real-time usage
5. **Regular cleanup**: `docker system prune` removes unused images/containers
6. **Backup volumes**: `docker volume ls` shows persistent data locations

---

## Next Steps

- [Getting Started Guide](../tutorial/getting-started.md): Complete setup walkthrough
- [Troubleshooting](troubleshooting.md): Fix common issues

---

**Remember:** FuzzForge's on-demand worker startup saves resources. You don't need to manually manage workers - the CLI does it automatically!
