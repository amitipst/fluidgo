#!/bin/bash
cd /opt/fluidgo/app
echo "=== Current commit on EC2 ==="
git log --oneline -5

echo ""
echo "=== Pulling latest ==="
git fetch origin main
git log --oneline origin/main -1

echo ""
echo "=== Rebuilding + restarting frontend and ollama ==="
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend ollama
sleep 5

echo ""
echo "=== Ollama container memory limit now ==="
docker inspect app-ollama-1 --format='{{.HostConfig.Memory}}' | awk '{print $1/1024/1024" MB"}'

echo ""
echo "=== Triggering a REAL AI generate call and watching memory live ==="
( for i in 1 2 3 4 5 6 7 8; do
    docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}" app-ollama-1
    sleep 3
  done ) &
STATS_PID=$!

curl -s -m 60 -X POST http://localhost:11434/api/generate \
  -d '{"model":"phi3:mini","prompt":"Say hello in one sentence.","stream":false}' \
  -o /tmp/ollama_test_response.json -w "\nHTTP_CODE=%{http_code} TIME=%{time_total}s\n"

wait $STATS_PID

echo ""
echo "=== Response body ==="
cat /tmp/ollama_test_response.json 2>/dev/null | head -c 500
echo ""

echo ""
echo "=== Ollama logs since the test ==="
docker compose -f docker-compose.prod.yml logs --tail=30 ollama

echo ""
echo "=== dmesg OOM check ==="
sudo dmesg -T 2>/dev/null | grep -i "killed process\|out of memory" | tail -5
