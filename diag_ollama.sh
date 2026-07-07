#!/bin/bash
echo "=== Ollama container status ==="
docker compose -f docker-compose.prod.yml ps ollama

echo ""
echo "=== Ollama logs (last 40 lines) ==="
docker compose -f docker-compose.prod.yml logs --tail=40 ollama

echo ""
echo "=== Is the model actually present? ==="
docker compose -f docker-compose.prod.yml exec -T ollama ollama list

echo ""
echo "=== Container memory limit vs actual usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "=== Host memory (confirms if resize to t3.large happened) ==="
free -h

echo ""
echo "=== dmesg OOM kills in last few hours ==="
sudo dmesg -T 2>/dev/null | grep -i "killed process\|out of memory" | tail -10
