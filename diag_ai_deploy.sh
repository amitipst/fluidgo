#!/bin/bash
cd /opt/fluidgo/app

echo "=== Is the fix actually deployed inside the running container? ==="
docker compose -f docker-compose.prod.yml exec -T backend grep -n "timeout=" app/services/ai_service.py

echo ""
echo "=== Backend container uptime (did it actually restart?) ==="
docker compose -f docker-compose.prod.yml ps backend

echo ""
echo "=== Local git commit vs what's on EC2 ==="
git log --oneline -1

echo ""
echo "=== Ollama status right now ==="
docker compose -f docker-compose.prod.yml ps ollama
curl -s -m 5 http://localhost:11434/api/tags

echo ""
echo "=== Backend logs, last 40 lines (looking for the actual exception) ==="
docker compose -f docker-compose.prod.yml logs --tail=40 backend
