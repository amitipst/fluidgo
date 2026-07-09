#!/bin/bash
cd /opt/fluidgo/app

echo "=== All meetings: who owns them? ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT m.company, u.name AS owner, u.role, u.business, u.region, m.date
   FROM meetings m JOIN users u ON u.id = m.user_id ORDER BY m.date DESC;"

echo ""
echo "=== Every active user's business + region (does it match Amit's?) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT name, role, business, region, manager_id IS NOT NULL AS has_manager
   FROM users WHERE is_active = true ORDER BY role, name;"

echo ""
echo "=== What business_head Amit would see as visible team (business match) ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT a.name AS amit, a.business AS amit_business,
          COUNT(u.id) AS visible_users
   FROM users a
   LEFT JOIN users u ON u.business = a.business AND u.is_active = true
   WHERE a.email = 'amit.singh@wepsol.com'
   GROUP BY a.name, a.business;"
