#!/bin/bash
# FuzzForge CI/CD Startup Script
# This script configures Docker and starts FuzzForge services for CI/CD environments
set -e

echo "🚀 Starting FuzzForge for CI/CD..."

# Configure Docker for insecure registry (required for localhost:5001)
echo "📝 Configuring Docker for local registry..."
if [ -f /etc/docker/daemon.json ]; then
    # Merge with existing config if jq is available
    if command -v jq &> /dev/null; then
        echo "  Merging with existing Docker config..."
        jq '. + {"insecure-registries": (."insecure-registries" // []) + ["localhost:5001"] | unique}' \
            /etc/docker/daemon.json > /tmp/daemon.json
        sudo mv /tmp/daemon.json /etc/docker/daemon.json
    else
        echo "  ⚠️  jq not found, overwriting Docker config (backup created)"
        sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.backup
        echo '{"insecure-registries": ["localhost:5001"]}' | sudo tee /etc/docker/daemon.json > /dev/null
    fi
else
    echo "  Creating new Docker config..."
    echo '{"insecure-registries": ["localhost:5001"]}' | sudo tee /etc/docker/daemon.json > /dev/null
fi

# Restart Docker daemon
echo "🔄 Restarting Docker daemon..."
if command -v systemctl &> /dev/null; then
    sudo systemctl restart docker
else
    sudo service docker restart
fi

# Wait for Docker to be ready
echo "⏳ Waiting for Docker to be ready..."
timeout 30 bash -c 'until docker ps &> /dev/null; do sleep 1; done' || {
    echo "❌ Docker failed to start"
    exit 1
}
echo "  ✓ Docker is ready"

# Start FuzzForge services
echo ""
echo "🐳 Starting FuzzForge services (core only, workers on-demand)..."
echo "  This will start:"
echo "    • Temporal (workflow engine)"
echo "    • PostgreSQL (Temporal database)"
echo "    • MinIO (object storage)"
echo "    • Backend (API server)"
echo ""

# Check if docker-compose or docker compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose not found"
    exit 1
fi

# Start services
$COMPOSE_CMD up -d

# Wait for backend health
echo ""
echo "⏳ Waiting for services to be healthy (up to 2 minutes)..."
echo "  Checking backend health at http://localhost:8000/health"
SECONDS=0
timeout 120 bash -c 'until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    if [ $((SECONDS % 10)) -eq 0 ]; then
        echo "  Still waiting... (${SECONDS}s elapsed)"
    fi
    sleep 3
done' || {
    echo ""
    echo "❌ Services failed to become healthy within 2 minutes"
    echo ""
    echo "Troubleshooting:"
    echo "  • Check logs: docker-compose logs"
    echo "  • Check status: docker-compose ps"
    echo "  • Check backend logs: docker logs fuzzforge-backend"
    exit 1
}

echo ""
echo "✅ FuzzForge is ready! (startup took ${SECONDS}s)"
echo ""
echo "📊 Service Status:"
$COMPOSE_CMD ps

echo ""
echo "🎯 Next steps:"
echo "  1. Initialize FuzzForge project:"
echo "     ff init --api-url http://localhost:8000"
echo ""
echo "  2. Run a security scan:"
echo "     ff workflow run security_assessment . --wait --fail-on critical,high"
echo ""
echo "  3. Export results:"
echo "     ff workflow run security_assessment . --wait --export-sarif results.sarif"
echo ""
