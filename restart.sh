#!/bin/bash
# Plane - restart all services (Docker + migrations)
# Usage: ./restart.sh

set -e
cd "$(dirname "$0")"

echo ""
echo "Plane: restarting all services..."
echo ""

# 1. Restart Docker Compose
echo "[1/3] Restarting Docker containers..."
docker compose -f docker-compose-local.yml restart
echo "Docker containers restarted."
echo ""

# 2. Wait for API/DB, then run migrations
echo "[2/3] Waiting 5s for services to start..."
sleep 5

echo "Running migrations..."
docker compose -f docker-compose-local.yml run --rm migrator || true
echo "Migrations done (or skipped)."
echo ""

# 3. Reminder for web
echo "[3/3] Done."
echo ""
echo "Start the web app (if needed):"
echo "  pnpm --filter=web dev"
echo ""
echo "Then open: http://127.0.0.1:3000"
echo ""
