#!/bin/bash
cd /opt/fluidgo/app

echo "=== 1. Does the running backend container match the latest git code? ==="
echo "Local git HEAD:"
git rev-parse --short HEAD
echo "dsr.py /history line in the RUNNING container:"
docker compose -f docker-compose.prod.yml exec -T backend grep -n "async def get_my_history" app/routers/dsr.py || echo "!! get_my_history NOT FOUND in container — stale image"

echo ""
echo "=== 2. Call /dsr/history AS ISHAANT directly against the API ==="
# Log in as Ishaant to get a token (adjust password if needed)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ishaant.hangloo@wepsol.com","password":"Welcome@123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "!! Could not log in as Ishaant (password may differ). Skipping API call."
  echo "   Try manually with his real password:"
  echo "   curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"ishaant.hangloo@wepsol.com\",\"password\":\"<PW>\"}'"
else
  echo "Got token. Calling /dsr/history?month=2026-07 ..."
  curl -s "http://localhost:8000/api/dsr/history?month=2026-07" \
    -H "Authorization: Bearer $TOKEN" \
    | python3 -m json.tool | head -40
fi

echo ""
echo "=== 3. Ishaant's exact bu value vs the scheme's bu (scheme scope bug) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT name, role, bu, region, business FROM users WHERE name ILIKE '%ishaant%';"
echo "Scheme audience:"
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT name, scope, bu, business, period, status FROM incentive_schemes WHERE period='2026-07';"
