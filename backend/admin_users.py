"""
Admin user management script for EC2.
Run: docker compose -f docker-compose.prod.yml exec -T backend python admin_users.py

Operations:
1. Update Amit's email → amit.singh@wepsol.com
2. Create 2 new users (edit the NEW_USERS list below)
"""
import asyncio, sys
sys.path.insert(0, '/app')

# ── Edit these 2 users to create ────────────────────────────────────────────
NEW_USERS = [
    {
        "name":     "Danish Sayyed",          # Full name
        "email":    "danish.sayyed@wepsol.com",  # Work email
        "password": "Fluid@2026!",            # Initial password (must change)
        "role":     "rep",                    # rep | inside_sales | pre_sales | manager
        "bu":       "West",
        "business": "fluidpro",
    },
    {
        "name":     "Rajesh Sharma",
        "email":    "rajesh.sharma@wepsol.com",
        "password": "Mgr@2026!",
        "role":     "manager",
        "bu":       "West",
        "business": "fluidpro",
    },
]
# ────────────────────────────────────────────────────────────────────────────

async def run():
    from app.database import AsyncSessionLocal
    from app.models import User
    from app.services.auth_service import hash_password
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:

        # 1. Update Amit's login email
        print("=== Updating Amit Singh's email ===")
        amit = (await db.execute(
            select(User).where(User.email == "amit@wepsol.com")
        )).scalar_one_or_none()

        if amit:
            old_email = amit.email
            amit.email    = "amit.singh@wepsol.com"
            amit.role     = "business_head"          # Global fluidPro BU Head
            amit.region   = "Global - fluidPro"      # Sees all India regions
            amit.bu       = "Global"                  # legacy field
            await db.flush()
            print(f"  ✅ Email: {old_email} → amit.singh@wepsol.com")
            print(f"  ✅ Role:  bu_head → business_head (sees all India regions)")
            print(f"  ✅ Region: Global - fluidPro")
        else:
            # Check if already updated
            amit2 = (await db.execute(
                select(User).where(User.email == "amit.singh@wepsol.com")
            )).scalar_one_or_none()
            if amit2:
                print(f"  ℹ️  Already updated to amit.singh@wepsol.com")
            else:
                print(f"  ❌ User amit@wepsol.com not found — check the DB")

        # 2. Create new users
        print("\n=== Creating new users ===")
        for u_data in NEW_USERS:
            existing = (await db.execute(
                select(User).where(User.email == u_data["email"])
            )).scalar_one_or_none()

            if existing:
                print(f"  ⚠️  {u_data['email']} already exists — skipping")
                continue

            new_user = User(
                name=u_data["name"],
                email=u_data["email"],
                password_hash=hash_password(u_data["password"]),
                role=u_data["role"],
                bu=u_data["bu"],
                business=u_data["business"],
                is_active=True
            )
            db.add(new_user)
            print(f"  ✅ Created: {u_data['name']} ({u_data['email']}) | {u_data['role']} | {u_data['bu']} BU")

        await db.commit()

        # 3. Show all active users
        print("\n=== Current Active Users ===")
        users = (await db.execute(
            select(User).where(User.is_active == True).order_by(User.role, User.name)
        )).scalars().all()
        for u in users:
            print(f"  {u.role:15s} | {u.name:25s} | {u.email}")

asyncio.run(run())
