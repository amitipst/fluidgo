#!/bin/bash
cd /opt/fluidgo/app

echo "=== Ishaant's user id + role/region/business ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT id, name, role, region, business FROM users WHERE name ILIKE '%ishaant%';"

echo ""
echo "=== Ishaant's DSR rows: dates, status, approval (does DSR history filter exclude them?) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT d.date, d.status, d.approval_status, d.calls, d.visits, d.followups, d.submitted_at
   FROM dsr_daily d JOIN users u ON u.id=d.user_id
   WHERE u.name ILIKE '%ishaant%' ORDER BY d.date DESC;"

echo ""
echo "=== What period string do those DSRs fall in? (checking 2026-07 match) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT to_char(d.date,'YYYY-MM') AS period, COUNT(*) 
   FROM dsr_daily d JOIN users u ON u.id=d.user_id
   WHERE u.name ILIKE '%ishaant%' GROUP BY period;"

echo ""
echo "=== Any incentive schemes at all? (Ishaant says he created one) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT id, name, period, status, scope, bu, business, created_by FROM incentive_schemes ORDER BY created_at DESC LIMIT 10;"

echo ""
echo "=== Schemes for period 2026-07 specifically ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT name, period, status, scope, bu, business FROM incentive_schemes WHERE period='2026-07';"
