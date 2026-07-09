#!/bin/bash
cd /opt/fluidgo/app
echo "=== Deactivated users matching old smoke-test emails ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT id, name, email, role, region, is_active, manager_id FROM users
   WHERE email IN ('manager@fluidpro.in','sanjay.ps@fluidpro.in','danish@fluidpro.in','inside@fluidpro.in');"
