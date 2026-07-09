#!/bin/bash
cd /opt/fluidgo/app
set -e
git pull

echo "=== Deploying backend changes (hot copy, no rebuild needed) ==="
docker cp backend/app/services/permission_service.py app-backend-1:/app/app/services/permission_service.py
docker cp backend/app/routers/dsr.py app-backend-1:/app/app/routers/dsr.py
docker cp backend/app/routers/users.py app-backend-1:/app/app/routers/users.py
docker cp backend/app/routers/auth.py app-backend-1:/app/app/routers/auth.py
docker compose -f docker-compose.prod.yml restart backend
sleep 3

echo "=== Rebuilding frontend (DSR History UI change needs a real build) ==="
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend

echo "=== Applying manager_id updates for Ishaant/Modassir/Sowmya ==="
bash set_amit_direct_reports.sh

echo ""
echo "=== Health check ==="
docker compose -f docker-compose.prod.yml ps
