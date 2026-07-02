from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import date
from typing import Optional
import uuid
from app.database import get_db
from app.models import User, DSRDaily, PipelineDeal, RevenueTarget
from app.services.deps import get_current_user, require_role
from app.services.rigor_service import calculate_rigor_score, rigor_label
from app.services.permission_service import resolve_visible_user_ids
from app.services.scoring_engine import _period_bounds

router = APIRouter()

@router.get("/rep/{user_id}")
async def rep_analytics(user_id: str, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    result = await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == uuid.UUID(user_id))
        .order_by(DSRDaily.date.asc())
    )
    dsrs = result.scalars().all()
    return [
        {**{c.name: getattr(d, c.name) for c in d.__table__.columns},
         "rigor_score": calculate_rigor_score(d),
         "rigor_label": rigor_label(calculate_rigor_score(d))}
        for d in dsrs
    ]

@router.get("/team")
async def team_analytics(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_role("manager", "bu_head"))):
    # Exited reps are soft-disabled (is_active=False), never deleted, so their historical
    # DSR/meeting/lead/pipeline data is untouched. Default view only shows the active
    # roster; pass include_inactive=true to also see exited reps' past performance.
    query = select(User) if include_inactive else select(User).where(User.is_active == True)
    users_result = await db.execute(query)
    users = users_result.scalars().all()
    out = []
    for u in users:
        dsrs_result = await db.execute(
            select(DSRDaily).where(DSRDaily.user_id == u.id)
        )
        dsrs = dsrs_result.scalars().all()
        working = [d for d in dsrs if d.status == "working"]
        avg_rigor = (sum(calculate_rigor_score(d) for d in working) / len(working)) if working else 0
        out.append({
            "user_id": str(u.id), "name": u.name, "role": u.role, "is_active": u.is_active,
            "total_days": len(dsrs), "working_days": len(working),
            "total_calls": sum(d.calls for d in dsrs),
            "total_visits": sum(d.visits for d in dsrs),
            "total_followups": sum(d.followups for d in dsrs),
            "total_leads": sum(d.new_leads for d in dsrs),
            "total_proposals": sum(d.proposals for d in dsrs),
            "avg_rigor": round(avg_rigor, 1),
            "rigor_label": rigor_label(int(avg_rigor))
        })
    return sorted(out, key=lambda x: x["avg_rigor"], reverse=True)

@router.get("/revenue")
async def revenue_analytics(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_role("manager", "bu_head"))):
    """Revenue Intelligence: forecast, target achievement, gap, pipeline coverage,
    win %, avg deal size — all derived from the extended `pipeline` table + the new
    config-driven revenue_targets table (no hardcoded targets)."""
    today = date.today()
    p = period or f"{today.year}-{today.month:02d}"
    start, end = _period_bounds(p)

    visible = await resolve_visible_user_ids(db, user)
    deal_query = select(PipelineDeal)
    if visible is not None:
        deal_query = deal_query.where(PipelineDeal.user_id.in_(visible))
    deals = (await db.execute(deal_query)).scalars().all()

    won = [d for d in deals if d.stage == "closed_won" and d.closure_eta and start <= d.closure_eta <= end]
    lost = [d for d in deals if d.stage == "closed_lost"]
    open_deals = [d for d in deals if d.stage not in ("closed_won", "closed_lost")]

    total_revenue = sum(float(d.deal_value or 0) for d in won)
    pipeline_value = sum(float(d.deal_value or 0) for d in open_deals)
    win_pct = (len(won) / (len(won) + len(lost)) * 100) if (won or lost) else 0.0
    avg_deal_size = (total_revenue / len(won)) if won else 0.0

    target_query = select(RevenueTarget).where(RevenueTarget.period == p)
    if visible is not None:
        target_query = target_query.where(RevenueTarget.user_id.in_(visible))
    total_target = sum(float(t.target_amount) for t in (await db.execute(target_query)).scalars().all())

    return {
        "period": p,
        "revenue": round(total_revenue, 2),
        "target": round(total_target, 2),
        "gap": round(total_target - total_revenue, 2),
        "target_achievement_pct": round((total_revenue / total_target * 100) if total_target else 0, 1),
        "pipeline_coverage_ratio": round((pipeline_value / total_target) if total_target else 0, 2),
        "win_pct": round(win_pct, 1),
        "avg_deal_size": round(avg_deal_size, 2),
        "open_deal_count": len(open_deals),
        "pipeline_value": round(pipeline_value, 2),
    }

class TargetIn(BaseModel):
    user_id: str
    period: str
    target_amount: float

@router.post("/revenue/targets")
async def set_revenue_target(body: TargetIn, db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_role("manager", "bu_head"))):
    """Config-driven targets — set here, never hardcoded. Upserts per (user, period)."""
    existing = (await db.execute(
        select(RevenueTarget).where(RevenueTarget.user_id == body.user_id, RevenueTarget.period == body.period)
    )).scalar_one_or_none()
    if existing:
        existing.target_amount = body.target_amount
    else:
        db.add(RevenueTarget(user_id=body.user_id, period=body.period, target_amount=body.target_amount))
    await db.commit()
    return body
