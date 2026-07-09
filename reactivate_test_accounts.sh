#!/bin/bash
cd /opt/fluidgo/app
set -e

echo "=== Reactivating manager/rep/pre_sales/inside_sales test accounts ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "UPDATE users SET is_active = true
   WHERE email IN ('manager@fluidpro.in','danish@fluidpro.in','sanjay.ps@fluidpro.in','inside@fluidpro.in');"

echo ""
echo "=== Resetting passwords to known smoke-test values ==="
docker compose -f docker-compose.prod.yml exec -T backend python3 -c "
from app.services.auth_service import hash_password
import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select, update
from app.models import User

CREDS = {
    'manager@fluidpro.in':   'Mgr@2026!',
    'danish@fluidpro.in':    'Fluid@2026!',
    'sanjay.ps@fluidpro.in': 'Fluid@2026!',
    'inside@fluidpro.in':    'Inside@2026!',
}

async def main():
    async with AsyncSessionLocal() as db:
        for email, pwd in CREDS.items():
            h = hash_password(pwd)
            await db.execute(update(User).where(User.email == email).values(password_hash=h))
        await db.commit()
        print('Passwords reset for:', list(CREDS.keys()))

asyncio.run(main())
"

echo ""
echo "=== Verify: active status + roles ==="
docker compose -f docker-compose.prod.yml exec -T db psql -U fluidgo fluidgo -c \
  "SELECT name, email, role, is_active FROM users
   WHERE email IN ('manager@fluidpro.in','danish@fluidpro.in','sanjay.ps@fluidpro.in','inside@fluidpro.in');"
