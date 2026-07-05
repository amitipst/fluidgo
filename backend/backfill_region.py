"""
One-off backfill: fix any users with region=NULL (legacy created before
migration 0009, or created via an old admin_users.py that didn't set region).
Run: docker compose -f docker-compose.prod.yml exec -T backend python backfill_region.py
"""
import asyncio, sys
sys.path.insert(0, '/app')

BU_TO_REGION = {
    "West":    "India - West",
    "North":   "India - North",
    "South":   "India - South",
    "East":    "India - East",
    "Central": "India - Central",
    "Global":  "Global - fluidPro",
}

async def run():
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        users = (await db.execute(
            select(User).where(User.region == None)
        )).scalars().all()

        print(f"Found {len(users)} users with NULL region")
        for u in users:
            new_region = BU_TO_REGION.get(u.bu, f"India - {u.bu}")
            print(f"  {u.name:25s} | bu={u.bu:10s} -> region={new_region}")
            u.region = new_region

        await db.commit()
        print(f"\n✅ Backfilled {len(users)} users")

        # Verify — show any remaining duplicates/inconsistencies
        print("\n=== Region distribution check ===")
        all_users = (await db.execute(
            select(User).where(User.is_active == True)
        )).scalars().all()
        regions = {}
        for u in all_users:
            r = u.region or "NULL"
            regions.setdefault(r, []).append(u.name)
        for region, names in sorted(regions.items()):
            print(f"  {region:22s} : {len(names)} users")

asyncio.run(run())
