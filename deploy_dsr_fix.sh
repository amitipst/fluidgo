#!/bin/bash
cd /opt/fluidgo/app
git pull
docker cp backend/app/routers/dsr.py app-backend-1:/app/app/routers/dsr.py
docker compose -f docker-compose.prod.yml restart backend
sleep 3
echo "=== Verifying fix: hitting /api/dsr/history requires auth so just check container is healthy ==="
docker compose -f docker-compose.prod.yml ps backend
