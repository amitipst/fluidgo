#!/bin/bash
cd /opt/fluidgo/app

echo "=== Run get_my_history logic directly for Ishaant (no login needed) ==="
docker compose -f docker-compose.prod.yml exec -T backend python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models import User, DSRDaily
from sqlalchemy import select, desc
from datetime import date
from calendar import monthrange

async def main():
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.name.ilike('%ishaant%')))).scalar_one_or_none()
        print('User:', u.name, '| id:', u.id, '| role:', u.role)

        # Replicate EXACT /dsr/history logic for month=2026-07
        month = '2026-07'
        q = select(DSRDaily).where(DSRDaily.user_id == u.id)
        yr, mo = int(month[:4]), int(month[5:7])
        start = date(yr, mo, 1)
        end = date(yr, mo, monthrange(yr, mo)[1])
        q = q.where(DSRDaily.date >= start, DSRDaily.date <= end)
        q = q.order_by(desc(DSRDaily.date)).limit(60)
        rows = (await db.execute(q)).scalars().all()
        print(f'Rows returned by history query for {month}: {len(rows)}')
        for r in rows:
            print(f'  date={r.date} status={r.status} approval={r.approval_status} calls={r.calls}')

        # Now try SERIALIZING each row — this is where a crash would silently empty the response
        from app.routers.dsr import _serialize_dsr
        from app.services.rigor_service import calculate_rigor_score
        from app.models import SelfScore
        print('--- Attempting serialization (catches any per-row error) ---')
        for r in rows:
            try:
                rigor = calculate_rigor_score(r)
                ss = (await db.execute(select(SelfScore).where(SelfScore.dsr_id == r.id))).scalar_one_or_none()
                d = _serialize_dsr(r, rigor, ss)
                print(f'  OK  date={r.date} rigor={d[\"rigor_score\"]}')
            except Exception as e:
                import traceback
                print(f'  !! SERIALIZE FAILED for date={r.date}: {type(e).__name__}: {e}')
                traceback.print_exc()

asyncio.run(main())
"
