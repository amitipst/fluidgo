#!/bin/bash
cd /opt/fluidgo/app

echo "=== Which commit is deployed? (need d77c302+ for the auth fix, 8a73e6c for latest) ==="
git log --oneline -3

echo ""
echo "=== Is the auth fix (auto_error=False) actually in the running container? ==="
docker compose -f docker-compose.prod.yml exec -T backend grep -n "auto_error" app/services/deps.py || echo "!! auto_error NOT found - deps.py fix is NOT deployed"

echo ""
echo "=== Recent lead-save errors in backend logs ==="
docker compose -f docker-compose.prod.yml logs --tail=120 backend | grep -iE "lead|422|401|403|500|validation|error" | tail -25

echo ""
echo "=== Lead table schema (is there a NOT NULL / constraint we're missing?) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name='leads' ORDER BY ordinal_position;"
