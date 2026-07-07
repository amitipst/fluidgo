"""
Non-destructive hygiene/integrity audit — read-only, makes zero changes.
Run: docker compose -f docker-compose.prod.yml exec -T backend python hygiene_check.py
"""
import asyncio, sys
sys.path.insert(0, '/app')

async def run():
    from app.database import AsyncSessionLocal
    from app.models import User, DSRDaily
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("1. ORPHANED manager_id (points to non-existent user)")
        print("=" * 60)
        all_ids = set((await db.execute(select(User.id))).scalars().all())
        users = (await db.execute(select(User))).scalars().all()
        orphan_mgr = [u for u in users if u.manager_id and u.manager_id not in all_ids]
        if orphan_mgr:
            for u in orphan_mgr:
                print(f"  ❌ {u.name} ({u.email}) manager_id={u.manager_id} does not exist")
        else:
            print("  ✅ none")

        print()
        print("=" * 60)
        print("2. manager_id points to a DEACTIVATED user")
        print("=" * 60)
        active_ids = {u.id for u in users if u.is_active}
        stale_mgr = [u for u in users if u.manager_id and u.manager_id in all_ids and u.manager_id not in active_ids]
        if stale_mgr:
            for u in stale_mgr:
                mgr = next((m for m in users if m.id == u.manager_id), None)
                print(f"  ⚠️  {u.name} reports to {mgr.name if mgr else '?'} — who is deactivated")
        else:
            print("  ✅ none")

        print()
        print("=" * 60)
        print("3. Duplicate emails (case-insensitive)")
        print("=" * 60)
        seen = {}
        for u in users:
            key = u.email.lower().strip()
            seen.setdefault(key, []).append(u.name)
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        if dupes:
            for email, names in dupes.items():
                print(f"  ❌ {email}: {names}")
        else:
            print("  ✅ none")

        print()
        print("=" * 60)
        print("4. Region / business consistency")
        print("=" * 60)
        bad_region = [u for u in users if u.is_active and not u.region]
        if bad_region:
            for u in bad_region:
                print(f"  ⚠️  {u.name} ({u.email}) has NULL region")
        else:
            print("  ✅ all active users have a region set")

        print()
        print("=" * 60)
        print("5. DSR rows referencing a non-existent user_id")
        print("=" * 60)
        dsr_user_ids = set((await db.execute(select(DSRDaily.user_id).distinct())).scalars().all())
        orphan_dsr_users = dsr_user_ids - all_ids
        if orphan_dsr_users:
            print(f"  ❌ {len(orphan_dsr_users)} DSR rows reference deleted user IDs: {orphan_dsr_users}")
        else:
            print("  ✅ none")

        print()
        print("=" * 60)
        print("6. DSR approved_by referencing a non-existent user")
        print("=" * 60)
        approved = (await db.execute(
            select(DSRDaily.approved_by).where(DSRDaily.approved_by.isnot(None)).distinct()
        )).scalars().all()
        bad_approvers = set(approved) - all_ids
        if bad_approvers:
            print(f"  ❌ approved_by references missing users: {bad_approvers}")
        else:
            print("  ✅ none")

        print()
        print("=" * 60)
        print("7. Role sanity — value not in known ROLE_HIERARCHY")
        print("=" * 60)
        from app.models import ROLE_HIERARCHY
        bad_roles = [u for u in users if u.role not in ROLE_HIERARCHY]
        if bad_roles:
            for u in bad_roles:
                print(f"  ❌ {u.name} has unknown role '{u.role}'")
        else:
            print("  ✅ all roles recognized")

        print()
        print("=" * 60)
        print("8. Active user / role summary")
        print("=" * 60)
        active = [u for u in users if u.is_active]
        by_role = {}
        for u in active:
            by_role.setdefault(u.role, []).append(u.name)
        for role, names in sorted(by_role.items()):
            print(f"  {role:15s} : {len(names)}  {names}")

        print()
        print("Done. This script made no changes.")

asyncio.run(run())
