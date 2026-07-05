"""
Admin user management script for EC2.
Run: docker compose -f docker-compose.prod.yml exec -T backend python admin_users.py

Operations:
1. Update Amit's email → amit.singh@wepsol.com, role → business_head
2. Create super_admin: itsupport.blr@wepsol.com
3. Create 2 new users (edit the NEW_USERS list below)
"""
import asyncio, sys
sys.path.insert(0, '/app')

# ── Super Admin (fixed credential — can be reassigned to anyone) ────────────
SUPER_ADMIN = {
    "name":     "IT Support",
    "email":    "itsupport.blr@wepsol.com",
    "password": "Temp@2026!",
    "role":     "super_admin",
    "bu":       "Global",
    "business": "fluidpro",
    "region":   "Global - fluidPro",
}

# ── Edit these 2 users to create ────────────────────────────────────────────
NEW_USERS = [
    {
        "name":     "Danish Sayyed",
        "email":    "danish.sayyed@wepsol.com",
        "password": "Fluid@2026!",
        "role":     "rep",
        "region":   "India - West",
        "business": "fluidpro",
    },
    {
        "name":     "Rajesh Sharma",
        "email":    "rajesh.sharma@wepsol.com",
        "password": "Mgr@2026!",
        "role":     "manager",
        "region":   "India - West",
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

        # 1. Update Amit's login email + role
        print("=== Updating Amit Singh's profile ===")
        amit = (await db.execute(
            select(User).where(User.email == "amit@wepsol.com")
        )).scalar_one_or_none()

        if amit:
            old_email = amit.email
            amit.email  = "amit.singh@wepsol.com"
            amit.role   = "business_head"
            amit.region = "Global - fluidPro"
            amit.bu     = "Global"
            await db.flush()
            print(f"  ✅ Email: {old_email} → amit.singh@wepsol.com")
            print(f"  ✅ Role:  business_head (Global fluidPro — all India regions)")
        else:
            amit2 = (await db.execute(
                select(User).where(User.email == "amit.singh@wepsol.com")
            )).scalar_one_or_none()
            if amit2:
                # Ensure role/region correct even if already migrated
                amit2.role   = "business_head"
                amit2.region = "Global - fluidPro"
                await db.flush()
                print(f"  ✅ Already at amit.singh@wepsol.com — role/region confirmed")
            else:
                print(f"  ❌ Amit not found under either email — check DB manually")

        # 2. Create super_admin (fixed IT support credential)
        print("\n=== Super Admin ===")
        existing_sa = (await db.execute(
            select(User).where(User.email == SUPER_ADMIN["email"])
        )).scalar_one_or_none()
        if existing_sa:
            existing_sa.role = "super_admin"
            existing_sa.is_active = True
            await db.flush()
            print(f"  ℹ️  {SUPER_ADMIN['email']} already exists — role confirmed as super_admin")
        else:
            sa_user = User(
                name=SUPER_ADMIN["name"],
                email=SUPER_ADMIN["email"],
                password_hash=hash_password(SUPER_ADMIN["password"]),
                role=SUPER_ADMIN["role"],
                bu=SUPER_ADMIN["bu"],
                region=SUPER_ADMIN["region"],
                business=SUPER_ADMIN["business"],
                is_active=True
            )
            db.add(sa_user)
            print(f"  ✅ Created: {SUPER_ADMIN['name']} ({SUPER_ADMIN['email']}) | super_admin")
            print(f"     Password: {SUPER_ADMIN['password']}  ⚠️  Change after first login")

        # 3. Create new users
        print("\n=== Creating new team members ===")
        for u_data in NEW_USERS:
            existing = (await db.execute(
                select(User).where(User.email == u_data["email"])
            )).scalar_one_or_none()
            if existing:
                print(f"  ⚠️  {u_data['email']} already exists — skipping")
                continue

            region = u_data.get("region", "India - West")
            new_user = User(
                name=u_data["name"],
                email=u_data["email"],
                password_hash=hash_password(u_data["password"]),
                role=u_data["role"],
                bu=region.split(" - ")[-1] if " - " in region else region,
                region=region,
                business=u_data["business"],
                is_active=True
            )
            db.add(new_user)
            print(f"  ✅ Created: {u_data['name']} ({u_data['email']}) | {u_data['role']} | {region}")

        await db.commit()

        # 4. Show all active users
        print("\n=== Current Active Users ===")
        users = (await db.execute(
            select(User).where(User.is_active == True).order_by(User.role, User.name)
        )).scalars().all()
        for u in users:
            region = getattr(u, "region", None) or u.bu
            print(f"  {u.role:15s} | {u.name:25s} | {region:20s} | {u.email}")

asyncio.run(run())
