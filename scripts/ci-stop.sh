#!/bin/bash
# FuzzForge CI/CD Cleanup Script
# This script stops and cleans up FuzzForge services after CI/CD execution
set -e

echo "🛑 Stopping FuzzForge services..."

# Check if docker-compose or docker compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "⚠️  docker-compose not found, skipping cleanup"
    exit 0
fi

# Stop and remove containers, networks, and volumes
echo "  Stopping containers..."
$COMPOSE_CMD down -v --remove-orphans

echo ""
echo "✅ FuzzForge stopped and cleaned up"
echo ""
echo "📊 Resources freed:"
echo "  • All containers removed"
echo "  • All volumes removed"
echo "  • All networks removed"
echo ""
