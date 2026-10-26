"""Trends (v1.5.0, 2026-10-26) — Amit: "reports and analysis should have weekly,
monthly, quarterly, annually, last 3 years … to see the trends of wins,
revenue, conversion, leads etc."

One read-only endpoint over data that already exists (meetings, leads, deals);
all bucketing and ratio maths lives in trend_service (unit-tested). Visibility
is the same single rule as Pipeline/Reports: governance blocked, owner scope via
resolve_visible_user_ids, seed and archived rows excluded.
"""
import csv
import io
from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Meeting, Lead, PipelineDeal
from app.services import trend_service as ts
from app.services.deps import get_current_user, deny_governance
from app.services.permission_service import resolve_visible_user_ids

router = APIRouter()
IST = ZoneInfo("Asia/Kolkata")

CSV_COLUMNS = ["period", "label", "meetings", "leads_created", "leads_converted", "lead_conversion_pct",
               "deals_created", "pipeline_added", "won_count", "won_arr", "won_one_time", "won_revenue",
               "lost_count", "win_rate_pct", "avg_deal_size", "invoiced_count", "invoiced_revenue"]


async def _compute(db: AsyncSession, user: User, granularity: str, periods: Optional[int]) -> dict:
    deny_governance(user)
    if granularity not in ts.GRANULARITIES:
        raise HTTPException(422, f"granularity must be one of {', '.join(ts.GRANULARITIES)}")
    n = periods or ts.DEFAULT_PERIODS[granularity]
    n = max(1, min(n, ts.MAX_PERIODS[granularity]))
    today = datetime.now(IST).date()
    start = ts.window_start(today, granularity, n)
    start_dt = datetime.combine(start, time.min, tzinfo=IST).astimezone(timezone.utc)
    visible = await resolve_visible_user_ids(db, user)

    mq = select(Meeting).where(Meeting.is_seed == False, Meeting.date >= start)
    lq = select(Lead).where(Lead.is_seed == False, Lead.date >= start)
    dq = select(PipelineDeal).where(
        PipelineDeal.is_seed == False, PipelineDeal.archived == False,
        or_(PipelineDeal.created_at >= start_dt, PipelineDeal.updated_at >= start_dt,
            PipelineDeal.closure_eta >= start, PipelineDeal.outcome_recorded_at >= start_dt,
            PipelineDeal.won_at >= start, PipelineDeal.invoiced_at >= start))
    if visible is not None:
        mq = mq.where(Meeting.user_id.in_(visible))
        lq = lq.where(Lead.user_id.in_(visible))
        dq = dq.where(PipelineDeal.user_id.in_(visible))

    meetings = (await db.execute(mq)).scalars().all()
    leads = (await db.execute(lq)).scalars().all()
    deals = (await db.execute(dq)).scalars().all()
    out = ts.build_trends(granularity, today, n, meetings=meetings, leads=leads, deals=deals)
    out["granularity"] = granularity
    return out


@router.get("")
async def get_trends(granularity: str = Query("monthly"), periods: Optional[int] = Query(None, ge=1),
                     db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """granularity: weekly | monthly | quarterly | yearly (India FY, Apr–Mar).
    Defaults: 12 weeks / 12 months / 8 quarters / 3 years. Zero-filled series."""
    return await _compute(db, user, granularity, periods)


@router.get("/export.csv")
async def export_trends_csv(granularity: str = Query("monthly"), periods: Optional[int] = Query(None, ge=1),
                            db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    data = await _compute(db, user, granularity, periods)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for r in data["series"]:
        w.writerow([r.get(c, "") if r.get(c) is not None else "" for c in CSV_COLUMNS])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="trends_{granularity}.csv"'})
