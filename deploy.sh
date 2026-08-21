#!/bin/bash
# =============================================================================
# Zero-Downtime Deployment Script
# Run on the VM after git pull (or triggered by CI/CD)
#
# What it does:
# 1. Pulls latest code from main
# 2. Rebuilds ONLY the backend container (Postgres/Redis stay running)
# 3. Runs Alembic migrations on startup
# 4. Optionally rebuilds frontend if frontend files changed
#
# Usage:
#   ./deploy.sh          # Deploy backend only (fast)
#   ./deploy.sh --all    # Rebuild everything including frontend
# =============================================================================

set -e

echo "=== RuDo by BizNDroid — Deployment ==="
echo ""

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Check what changed
FRONTEND_CHANGED=$(git diff HEAD~1 --name-only | grep "^frontend/" || true)

if [ "$1" == "--all" ] || [ -n "$FRONTEND_CHANGED" ]; then
    echo "🔨 Frontend changes detected — rebuilding frontend + backend..."
    docker compose -f docker-compose.prod.yml build frontend-builder backend
    docker compose -f docker-compose.prod.yml up -d frontend-builder
    # Wait for frontend build to complete
    sleep 5
    docker compose -f docker-compose.prod.yml up -d --no-deps backend
else
    echo "🔨 Rebuilding backend only (zero-downtime)..."
    docker compose -f docker-compose.prod.yml build backend
    docker compose -f docker-compose.prod.yml up -d --no-deps backend
fi

echo ""
echo "⏳ Waiting for backend health check..."
sleep 10

# Verify health
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy!"
else
    echo "❌ Backend health check failed. Check logs:"
    echo "   docker compose -f docker-compose.prod.yml logs backend --tail 50"
    exit 1
fi

echo ""
echo "🎉 Deployment complete!"
echo "   Frontend: https://${DOMAIN:-localhost}"
echo "   Backend:  https://${DOMAIN:-localhost}/api/health"
echo ""
