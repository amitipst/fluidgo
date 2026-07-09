#!/bin/bash
cd /opt/fluidgo/app
echo "=== All active users, by role ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT name, email, role, region, is_active FROM users WHERE is_active = true ORDER BY role, name;"
