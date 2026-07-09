#!/bin/bash
cd /opt/fluidgo/app
echo "=== Last 200 lines of backend logs, filtered for traceback/dsr/history ==="
docker compose -f docker-compose.prod.yml logs --tail=500 backend 2>&1 | grep -A 30 -B 5 "dsr/history\|Traceback" | tail -200
