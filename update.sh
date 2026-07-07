#!/bin/bash
# fluidGo EC2 Update Script — run this in VS Code terminal on EC2
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/amitipst/fluidgo/main/update.sh)
set -e

cd /opt/fluidgo/app

echo "=== [0/8] Backing up today's UAT database (safety net) ==="
mkdir -p /opt/fluidgo/backups
BACKUP_FILE="/opt/fluidgo/backups/backup_$(date +%Y%m%d_%H%M%S).sql"
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U fluidgo fluidgo > "$BACKUP_FILE"
echo "Backup saved: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

echo ""
echo "=== [1/8] Pulling latest code ==="
git fetch origin main
git reset --hard origin/main
echo "At commit: $(git log --oneline -1)"

echo ""
echo "=== [2/8] Container status ==="
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== [3/8] Running DB migrations ==="
docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

echo ""
echo "=== [4/8] Running admin_users.py (email/role sync) ==="
# Copy latest version into container then run
docker cp backend/admin_users.py app-backend-1:/app/admin_users.py 2>/dev/null || true
docker compose -f docker-compose.prod.yml exec -T backend python admin_users.py

echo ""
echo "=== [4b/8] Backfilling any NULL region users ==="
docker cp backend/backfill_region.py app-backend-1:/app/backfill_region.py 2>/dev/null || true
docker compose -f docker-compose.prod.yml exec -T backend python backfill_region.py

echo ""
echo "=== [5/8] Rebuilding images ==="
docker compose -f docker-compose.prod.yml build backend frontend

echo ""
echo "=== [6/8] Restarting all services ==="
docker compose -f docker-compose.prod.yml up -d
sleep 20

echo ""
echo "=== [7/8] Health checks & smoke test ==="
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
echo "=== [8/8] Performance snapshot (for the slowness UAT flagged) ==="
echo "--- Container resource usage (CPU / MEM) ---"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo ""
echo "--- Disk / swap ---"
free -h
df -h /opt/fluidgo
echo ""
echo "--- Timed sample requests ---"
echo -n "health: "; curl -s -o /dev/null -w "%{time_total}s\n" http://localhost:8000/api/health
echo -n "login page (frontend): "; curl -s -o /dev/null -w "%{time_total}s\n" http://localhost/

echo ""
echo "=============================="
echo "  Update complete!"
echo "  http://65.2.205.77"
echo "=============================="
