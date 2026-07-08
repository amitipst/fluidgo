#!/bin/bash
cd /opt/fluidgo/app

echo "=== Current migration head (should be 0012) ==="
docker compose -f docker-compose.prod.yml exec -T backend alembic current

echo ""
echo "=== Does target_type column exist on revenue_targets? ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='revenue_targets' ORDER BY ordinal_position;"

echo ""
echo "=== If 0012 is NOT applied, run it now ==="
docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec -T backend alembic current

echo ""
echo "=== Backend logs: last target-save error ==="
docker compose -f docker-compose.prod.yml logs --tail=80 backend | grep -iE "target|500|error|column|traceback" | tail -20

echo ""
echo "=== Analytics: is there any DSR data at all for the current user? ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT u.name, COUNT(d.id) as dsr_count FROM users u LEFT JOIN dsr_daily d ON d.user_id=u.id WHERE u.is_active=true GROUP BY u.name ORDER BY dsr_count DESC;"
