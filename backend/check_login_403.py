"""
Diagnose why smoke_test.py's login checks return 403 for
manager/rep/pre_sales/inside_sales — checks is_active + recent audit trail.
Run: docker compose -f docker-compose.prod.yml exec -T backend python check_login_403.py
"""
import asyncio, sys
sys.path.insert(0, '/app')

async def run():
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select, desc
    from datetime import datetime, timedelta

    async with AsyncSessionLocal() as db:
        print("=== All users: active status ===")
        users = (await db.execute(select(User).order_by(User.role, User.name))).scalars().all()
        for u in users:
            flag = "active" if u.is_active else "DEACTIVATED"
            print(f"  {u.role:15s} | {u.name:25s} | {u.email:30s} | {flag}")

        print("")
        print("=== Audit trail: last 24h user-related events ===")
        from app.models.audit import AuditLog
        rows = (await db.execute(
            select(AuditLog)
            .where(AuditLog.created_at >= datetime.utcnow() - timedelta(hours=24))
            .where(AuditLog.entity_type == "user")
            .order_by(desc(AuditLog.created_at))
        )).scalars().all()
        if not rows:
            print("  (no user-related audit events in last 24h)")
        for r in rows:
            print(f"  {r.created_at} | {r.user_email:30s} | {r.action:10s} | {r.summary}")

asyncio.run(run())
