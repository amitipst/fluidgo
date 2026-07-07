"""
One-off: promote Gaurav Nigam (COO) above business_head in the hierarchy,
and link Amit's manager_id to him so the reporting line is explicit in the org chart.

This has to run as a direct script rather than through the Team edit UI because
no one below level 45 (coo) is allowed to grant a role at or above that level —
that's the correct hierarchy rule we just added, not a bug.

Run: docker compose -f docker-compose.prod.yml exec -T backend python promote_coo.py
"""
import asyncio, sys
sys.path.insert(0, '/app')

GAURAV_EMAIL = "gaurav.nigam@wepsol.com"
AMIT_EMAIL   = "amit.singh@wepsol.com"

async def run():
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        gaurav = (await db.execute(
            select(User).where(User.email == GAURAV_EMAIL)
        )).scalar_one_or_none()

        if not gaurav:
            print(f"❌ {GAURAV_EMAIL} not found — check the email or create the account first.")
            return

        old_role = gaurav.role
        gaurav.role = "coo"
        # COO sees across every business — not scoped to one, so leave `business` as-is
        # (informational only; scope="all" ignores it) but region should read company-wide.
        gaurav.region = "Global - fluidPro"
        await db.flush()
        print(f"✅ {gaurav.name} ({GAURAV_EMAIL}): role changed {old_role} → coo")

        amit = (await db.execute(
            select(User).where(User.email == AMIT_EMAIL)
        )).scalar_one_or_none()

        if amit:
            amit.manager_id = gaurav.id
            print(f"✅ {amit.name}'s manager_id set to {gaurav.name} — reporting line now explicit")
        else:
            print(f"⚠️  {AMIT_EMAIL} not found — manager_id link skipped")

        await db.commit()

        print("\n=== Verify ===")
        for email in (GAURAV_EMAIL, AMIT_EMAIL):
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if u:
                mgr = None
                if u.manager_id:
                    mgr = (await db.execute(select(User).where(User.id == u.manager_id))).scalar_one_or_none()
                print(f"  {u.name:20s} | role={u.role:12s} | region={u.region:20s} | manager={mgr.name if mgr else '—'}")

asyncio.run(run())
