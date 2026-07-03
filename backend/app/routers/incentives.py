"""Incentive Schemes & Gamification router.

Who can create schemes:
  manager  → scope='team', within their own BU
  bu_head  → scope='bu', for their entire BU
  ceo/super_admin → any BU, any business

Reps see their own progress. Leaderboard visible to all in the BU.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import (User, IncentiveScheme, PointsLedger, UserBadge,
                         DSRDaily, Meeting, PipelineDeal, role_level)
from app.services.deps import get_current_user, require_level
from app.services.rigor_service import calculate_rigor_score, bant_score

router = APIRouter()

# ── Badge catalogue ───────────────────────────────────────────────────────────
BADGES = {
    "hat_trick":      {"name": "🎩 Hat Trick",       "desc": "3 deals closed in a month"},
    "first_deal":     {"name": "⭐ First Deal",       "desc": "First ever closed-won"},
    "streak_5":       {"name": "🔥 5-Day Streak",     "desc": "DSR submitted 5 days straight"},
    "streak_10":      {"name": "🔥🔥 10-Day Streak",  "desc": "DSR submitted 10 days straight"},
    "lead_machine":   {"name": "🎯 Lead Machine",     "desc": "10+ new leads in a month"},
    "bant_master":    {"name": "🧠 BANT Master",      "desc": "5+ fully-qualified BANT meetings"},
    "consistent":     {"name": "🏅 Consistent",       "desc": "Rigor > 70 for 3 months straight"},
    "deal_king":      {"name": "👑 Deal King",         "desc": "Highest revenue in BU for the month"},
    "rigor_champ":    {"name": "⚡ Rigor Champion",   "desc": "Rigor score > 90 for the month"},
    "top_caller":     {"name": "📞 Top Caller",       "desc": "Most calls in BU for the month"},
}

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class SchemeCreate(BaseModel):
    name:         str
    description:  Optional[str] = None
    period:       str  # "2026-07"
    scope:        Literal["team", "bu"] = "bu"
    metric:       str  # "calls"|"visits"|"new_leads"|"proposals"|"rigor_avg"|"followups"|"bant_meetings"|"closed_won_value"
    target_value: float
    reward_type:  Literal["cash", "points", "badge", "recognition"] = "points"
    reward_value: Optional[float] = None
    reward_badge: Optional[str]  = None

class SchemeUpdate(BaseModel):
    name:         Optional[str] = None
    description:  Optional[str] = None
    status:       Optional[Literal["active", "paused", "closed"]] = None

# ── Helpers ───────────────────────────────────────────────────────────────────
async def _compute_metric(db: AsyncSession, user: User, period: str, metric: str) -> float:
    """Compute a single metric value for a user in a given period."""
    from app.services.scoring_engine import _period_bounds
    start, end = _period_bounds(period)
    dsrs = (await db.execute(
        select(DSRDaily).where(
            DSRDaily.user_id == user.id,
            DSRDaily.date >= start, DSRDaily.date <= end
        )
    )).scalars().all()

    if metric == "calls":       return float(sum(d.calls for d in dsrs))
    if metric == "visits":      return float(sum(d.visits for d in dsrs))
    if metric == "new_leads":   return float(sum(d.new_leads for d in dsrs))
    if metric == "proposals":   return float(sum(d.proposals for d in dsrs))
    if metric == "followups":   return float(sum(d.followups for d in dsrs))
    if metric == "rigor_avg":
        working = [d for d in dsrs if d.status == "working"]
        from app.services.rigor_service import calculate_rigor_score
        return (sum(calculate_rigor_score(d) for d in working) / len(working)) if working else 0.0
    if metric == "bant_meetings":
        meetings = (await db.execute(
            select(Meeting).where(
                Meeting.user_id == user.id,
                Meeting.date >= start, Meeting.date <= end,
                Meeting.bant_budget == True, Meeting.bant_authority == True,
                Meeting.bant_need == True, Meeting.bant_timeline == True
            )
        )).scalars().all()
        return float(len(meetings))
    if metric == "closed_won_value":
        deals = (await db.execute(
            select(PipelineDeal).where(
                PipelineDeal.user_id == user.id,
                PipelineDeal.stage == "closed_won",
                PipelineDeal.closure_eta >= start, PipelineDeal.closure_eta <= end
            )
        )).scalars().all()
        return float(sum(float(d.deal_value or 0) for d in deals))
    return 0.0

def _serialize_scheme(s: IncentiveScheme) -> dict:
    return {
        "id": str(s.id), "name": s.name, "description": s.description,
        "period": s.period, "scope": s.scope, "status": s.status,
        "metric": s.metric, "target_value": float(s.target_value),
        "reward_type": s.reward_type,
        "reward_value": float(s.reward_value) if s.reward_value else None,
        "reward_badge": s.reward_badge,
        "bu": s.bu, "business": s.business,
        "created_at": s.created_at.isoformat()
    }

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/schemes")
async def list_schemes(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """List active schemes for this user's BU."""
    query = select(IncentiveScheme).where(
        IncentiveScheme.bu == user.bu,
        IncentiveScheme.business == user.business,
        IncentiveScheme.status == "active"
    )
    if period:
        query = query.where(IncentiveScheme.period == period)
    schemes = (await db.execute(query)).scalars().all()
    return [_serialize_scheme(s) for s in schemes]

@router.post("/schemes")
async def create_scheme(body: SchemeCreate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_level(20))):
    """Manager/BU Head creates an incentive scheme."""
    s = IncentiveScheme(
        created_by=user.id, bu=user.bu, business=user.business,
        scope=body.scope, name=body.name, description=body.description,
        period=body.period, status="active", metric=body.metric,
        target_value=body.target_value, reward_type=body.reward_type,
        reward_value=body.reward_value, reward_badge=body.reward_badge
    )
    db.add(s)
    await db.commit()
    return _serialize_scheme(s)

@router.patch("/schemes/{scheme_id}")
async def update_scheme(scheme_id: str, body: SchemeUpdate,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_level(20))):
    s = (await db.execute(
        select(IncentiveScheme).where(IncentiveScheme.id == uuid.UUID(scheme_id))
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scheme not found")
    if s.bu != user.bu and role_level(user.role) < 50:
        raise HTTPException(403, "Cannot modify schemes from other BUs")
    if body.name:   s.name = body.name
    if body.description is not None: s.description = body.description
    if body.status: s.status = body.status
    await db.commit()
    return _serialize_scheme(s)

@router.get("/leaderboard")
async def leaderboard(period: str, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Points leaderboard for the BU in this period."""
    # Sum points per user in this period within this BU
    # Leaderboard only includes field roles — exclude HR, Finance, and support
    FIELD_ROLES = {"rep", "inside_sales", "pre_sales", "manager"}
    bu_users = (await db.execute(
        select(User).where(
            User.bu == user.bu,
            User.business == user.business,
            User.is_active == True,
            User.role.in_(FIELD_ROLES)
        )
    )).scalars().all()

    rows = []
    for u in bu_users:
        # Points from ledger
        points_result = await db.execute(
            select(func.coalesce(func.sum(PointsLedger.points), 0))
            .where(PointsLedger.user_id == u.id, PointsLedger.period == period)
        )
        total_points = int(points_result.scalar() or 0)

        # Badges earned this period
        badges = (await db.execute(
            select(UserBadge).where(UserBadge.user_id == u.id, UserBadge.period == period)
        )).scalars().all()

        rows.append({
            "user_id": str(u.id), "name": u.name, "role": u.role,
            "points": total_points,
            "badges": [{"key": b.badge_key, "name": b.badge_name} for b in badges],
            "badge_count": len(badges)
        })

    return sorted(rows, key=lambda x: (-x["points"], -x["badge_count"]))

@router.get("/my-progress")
async def my_progress(period: str, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Returns this rep's progress against all active schemes in the period."""
    schemes = (await db.execute(
        select(IncentiveScheme).where(
            IncentiveScheme.bu == user.bu,
            IncentiveScheme.business == user.business,
            IncentiveScheme.period == period,
            IncentiveScheme.status == "active"
        )
    )).scalars().all()

    progress = []
    for s in schemes:
        current = await _compute_metric(db, user, period, s.metric)
        pct = min(100.0, (current / float(s.target_value)) * 100) if s.target_value else 0
        achieved = current >= float(s.target_value)
        progress.append({
            **_serialize_scheme(s),
            "current_value": current,
            "progress_pct": round(pct, 1),
            "achieved": achieved
        })

    # Points total
    points_total = int((await db.execute(
        select(func.coalesce(func.sum(PointsLedger.points), 0))
        .where(PointsLedger.user_id == user.id, PointsLedger.period == period)
    )).scalar() or 0)

    badges = (await db.execute(
        select(UserBadge).where(UserBadge.user_id == user.id, UserBadge.period == period)
    )).scalars().all()

    return {
        "period": period,
        "points": points_total,
        "badges": [{"key": b.badge_key, "name": b.badge_name} for b in badges],
        "schemes": progress
    }

@router.get("/badges")
async def list_badges():
    """Return the full badge catalogue."""
    return [{"key": k, **v} for k, v in BADGES.items()]

@router.post("/award-badge")
async def award_badge(user_id: str, badge_key: str, period: str,
                      db: AsyncSession = Depends(get_db),
                      actor: User = Depends(require_level(20))):
    """Manually award a badge (manager+). Idempotent."""
    if badge_key not in BADGES:
        raise HTTPException(400, f"Unknown badge: {badge_key}")
    badge_info = BADGES[badge_key]
    # Upsert
    existing = (await db.execute(
        select(UserBadge).where(
            UserBadge.user_id == uuid.UUID(user_id),
            UserBadge.badge_key == badge_key,
            UserBadge.period == period
        )
    )).scalar_one_or_none()
    if not existing:
        db.add(UserBadge(user_id=uuid.UUID(user_id),
                          badge_key=badge_key, badge_name=badge_info["name"], period=period))
        await db.commit()
    return {"awarded": True, "badge": badge_info}
