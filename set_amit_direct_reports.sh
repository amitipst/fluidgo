#!/bin/bash
cd /opt/fluidgo/app
set -e

echo "=== Setting manager_id -> Amit Singh for Ishaant, Modassir, Sowmya ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c "
UPDATE users SET manager_id = (SELECT id FROM users WHERE email = 'amit.singh@wepsol.com')
WHERE email IN ('ishaant.hangloc@wepsol.com','modassir.tanweer@wepsol.com','Sowmya.Narayan@wepsol.com');
"

echo ""
echo "=== Verify ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c "
SELECT u.name, u.email, u.role, m.name AS reports_to
FROM users u LEFT JOIN users m ON m.id = u.manager_id
WHERE u.email IN ('ishaant.hangloc@wepsol.com','modassir.tanweer@wepsol.com','Sowmya.Narayan@wepsol.com');
"
