#!/bin/bash
# fluidGo EC2 Update Script — run this in VS Code terminal on EC2
# Usage: bash /opt/fluidgo/update.sh
set -e

cd /opt/fluidgo/app

echo "=== [1/6] Pulling latest code ==="
git fetch origin main
git reset --hard origin/main
echo "At commit: $(git log --oneline -1)"

echo ""
echo "=== [2/6] Container status before ==="
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== [3/6] Running DB migrations ==="
docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

echo ""
echo "=== [4/6] Rebuilding backend ==="
docker compose -f docker-compose.prod.yml build backend

echo ""
echo "=== [5/6] Restarting backend ==="
docker compose -f docker-compose.prod.yml up -d backend
sleep 15

echo ""
echo "=== [6/6] Health checks ==="
curl -s http://localhost:8000/api/health
echo ""
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== Smoke test ==="
docker compose -f docker-compose.prod.yml exec -T backend \
  python smoke_test.py --base http://localhost:8000

echo ""
echo "=== Ollama model status ==="
OLLAMA=$(docker ps --filter name=ollama --format "{{.Names}}" | grep -v init | head -1)
docker exec "$OLLAMA" ollama list 2>/dev/null || echo "Ollama: model not yet pulled"

echo ""
echo "=============================="
echo "  Update complete!"
echo "  Open http://65.2.205.77"
echo "=============================="
