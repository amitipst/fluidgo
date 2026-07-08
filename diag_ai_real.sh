#!/bin/bash
cd /opt/fluidgo/app

echo "=== Did migrations 0010 + 0011 actually apply? ==="
docker compose -f docker-compose.prod.yml exec -T backend alembic current

echo ""
echo "=== The actual failed AI insight error_detail (the real error, finally) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT status, LEFT(error_detail, 300) AS error, generated_at FROM ai_insights WHERE entity_type='dashboard' ORDER BY generated_at DESC NULLS LAST LIMIT 5;"

echo ""
echo "=== Backend logs around the AI generation (last 60) ==="
docker compose -f docker-compose.prod.yml logs --tail=60 backend | grep -iE "ai|ollama|insight|error|traceback|exception" | tail -30

echo ""
echo "=== Direct model timing: how long does phi3:mini ACTUALLY take for a real-sized prompt? ==="
time curl -s -X POST http://localhost:11434/api/generate \
  -d '{"model":"phi3:mini","prompt":"Analyse this sales rep: 36 calls, 1 visit, 14 followups, 6 leads, rigor 56/100. Give rigor assessment, top 2 deal priorities, critical gaps, one coaching observation.","stream":false,"keep_alive":"30m","options":{"num_predict":350}}' \
  -o /tmp/timing_test.json -w "\nHTTP=%{http_code} TIME=%{time_total}s\n"
echo "Response length: $(wc -c < /tmp/timing_test.json) bytes"
