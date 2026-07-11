"""
Read-only diagnostic: finds any revenue_targets rows whose `period` is NOT
a valid "YYYY-MM" monthly string (e.g. a stray literal "2026" or "2026-Q2"
row created before the quarterly editor fix). These rows are invisible to
both Analytics and the new Quarterly Target Editor — this script only
REPORTS them, it does not delete or modify anything.

Run inside the backend container:
  docker compose -f docker-compose.prod.yml exec -T backend python check_stray_targets.py
"""
import asyncio
import re
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import RevenueTarget, User

MONTHLY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(RevenueTarget))).scalars().all()
        stray = [r for r in rows if not MONTHLY_RE.match(r.period)]
        print(f"Total revenue_targets rows: {len(rows)}")
        print(f"Stray (non-monthly period) rows: {len(stray)}")
        if not stray:
            print("Nothing to clean up — all target rows are proper monthly grain.")
            return
        users = {u.id: u for u in (await db.execute(select(User))).scalars().all()}
        for r in stray:
            u = users.get(r.user_id)
            print(f"  id={r.id}  user={u.email if u else r.user_id}  "
                  f"period='{r.period}'  type={r.target_type}  amount={r.target_amount}")
        print("\nThese rows are orphaned and safe to delete once you've confirmed")
        print("their values were already re-entered via the new Quarterly editor.")

if __name__ == "__main__":
    asyncio.run(main())
