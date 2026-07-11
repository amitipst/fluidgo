"""
Reactivates the 4 UAT/smoke-test accounts if they've been deactivated
(is_active=False), which produces the 403 "account deactivated" errors
seen in smoke_test.py's Authentication section. This mirrors the same
fix applied on 2026-07-09 (Ishaant login issue session) — it seems to
recur, most likely something toggles is_active on these accounts between
sessions. Only touches is_active; does not change passwords or roles.

Run inside the backend container:
  docker compose -f docker-compose.prod.yml exec -T backend python reactivate_smoke_accounts.py
"""
import asyncio, sys
sys.path.insert(0, '/app')

SMOKE_TEST_EMAILS = [
    "manager@fluidpro.in",
    "danish@fluidpro.in",
    "sanjay.ps@fluidpro.in",
    "inside@fluidpro.in",
]

async def run():
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        for email in SMOKE_TEST_EMAILS:
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not u:
                print(f"  ❌ {email} — not found in DB at all")
                continue
            if u.is_active:
                print(f"  ✅ {email} — already active (role={u.role})")
            else:
                u.is_active = True
                print(f"  🔄 {email} — was deactivated, reactivated (role={u.role})")
        await db.commit()
        print("\nDone.")

asyncio.run(run())
