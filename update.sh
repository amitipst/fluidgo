#!/bin/bash
# fluidGo EC2 Update Script — run this in VS Code terminal on EC2
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/amitipst/fluidgo/main/update.sh)
set -e

cd /opt/fluidgo/app

echo "=== [1/7] Pulling latest code ==="
git fetch origin main
git reset --hard origin/main
echo "At commit: $(git log --oneline -1)"

echo ""
echo "=== [2/7] Container status ==="
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== [3/7] Running DB migrations ==="
docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

echo ""
echo "=== [4/7] Running admin_users.py (email/role sync) ==="
# Copy latest version into container then run
docker cp backend/admin_users.py app-backend-1:/app/admin_users.py 2>/dev/null || true
docker compose -f docker-compose.prod.yml exec -T backend python admin_users.py

echo ""
echo "=== [5/7] Rebuilding images ==="
docker compose -f docker-compose.prod.yml build backend frontend

echo ""
echo "=== [6/7] Restarting all services ==="
docker compose -f docker-compose.prod.yml up -d
sleep 20

echo ""
echo "=== [7/7] Health checks & smoke test ==="
curl -s http://localhost:8000/api/health && echo ""
docker compose -f docker-compose.prod.yml ps
echo ""
docker compose -f docker-compose.prod.yml exec -T backend \
  python smoke_test.py --base http://localhost:8000

echo ""
echo "=== Ollama model status ==="
OLLAMA=$(docker ps --filter name=ollama --format "{{.Names}}" | grep -v init | head -1)
if [ -n "$OLLAMA" ]; then
  docker exec "$OLLAMA" ollama list 2>/dev/null || echo "Ollama: checking..."
fi

echo ""
echo "=============================="
echo "  Update complete!"
echo "  http://65.2.205.77"
echo "=============================="
