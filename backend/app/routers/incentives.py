"""Incentive Schemes & Gamification router.

Who can create schemes:
  manager           → scope='team', within their own region
  regional_manager   → scope='region', for their entire region (formerly mislabeled 'bu_head')
  ceo/super_admin    → any region, any business

Reps see their own progress. Leaderboard visible to all in the region.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import (User, IncentiveScheme, PointsLedger, UserBadge, SchemeWinner,
                         DSRDaily, Meeting, PipelineDeal, role_level)
from app.services.deps import get_current_user, require_level
from app.services.permission_service import resolve_visible_user_ids
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
    """List active schemes visible to this user.
    A scheme is visible if it's in the user's business AND either targets the
    user's specific BU or is a business-wide scheme (bu='Global'). This is why
    a rep in 'North' still sees a 'Global'-scoped scheme created by a BU head."""
    from sqlalchemy import or_
    query = select(IncentiveScheme).where(
        IncentiveScheme.business == user.business,
        IncentiveScheme.status == "active",
        or_(
            IncentiveScheme.bu == user.bu,
            IncentiveScheme.bu == "Global",
            IncentiveScheme.scope == "business",
        ),
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
    from sqlalchemy import or_
    schemes = (await db.execute(
        select(IncentiveScheme).where(
            IncentiveScheme.business == user.business,
            IncentiveScheme.period == period,
            IncentiveScheme.status == "active",
            or_(
                IncentiveScheme.bu == user.bu,
                IncentiveScheme.bu == "Global",
                IncentiveScheme.scope == "business",
            ),
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


# ─────────────────────────────────────────────────────────────────────────────
# Scheme winner validation — HR sign-off gate before cash payout
# ─────────────────────────────────────────────────────────────────────────────

class WinnerReviewIn(BaseModel):
    action:  Literal["approve", "reject"]
    comment: Optional[str] = None


def _serialize_winner(w: SchemeWinner, rep_name: str = None, scheme_name: str = None) -> dict:
    return {
        "id": str(w.id), "scheme_id": str(w.scheme_id), "user_id": str(w.user_id),
        "rep_name": rep_name, "scheme_name": scheme_name,
        "period": w.period,
        "achieved_value": float(w.achieved_value), "target_value": float(w.target_value),
        "reward_type": w.reward_type,
        "reward_value": float(w.reward_value) if w.reward_value is not None else None,
        "reward_badge": w.reward_badge,
        "status": w.status,
        "hr_comment": w.hr_comment,
        "hr_reviewed_at": w.hr_reviewed_at.isoformat() if w.hr_reviewed_at else None,
        "paid": w.paid,
        "paid_at": w.paid_at.isoformat() if w.paid_at else None,
        "detected_at": w.detected_at.isoformat() if w.detected_at else None,
    }


@router.post("/schemes/{scheme_id}/detect-winners")
async def detect_winners(scheme_id: str, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_level(20))):
    """Scan every field-role user this scheme applies to; for anyone who has
    hit target and doesn't already have a SchemeWinner row for this scheme+
    period, create one. This is the ONLY place PointsLedger/UserBadge
    actually get written — Gamification.tsx's progress view only ever
    COMPUTED 'achieved' on the fly, nothing was ever persisted or paid out.
    Points/badge/recognition credit immediately (low-stakes, auto-approved);
    cash stops at status='pending_hr' — see review_winner below. Same
    same-BU-or-above-level authorization as update_scheme."""
    s = (await db.execute(select(IncentiveScheme).where(IncentiveScheme.id == uuid.UUID(scheme_id)))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scheme not found")
    if s.bu != user.bu and role_level(user.role) < 50:
        raise HTTPException(403, "Cannot detect winners for schemes outside your BU")

    FIELD_ROLES = {"rep", "inside_sales", "pre_sales", "manager"}
    from sqlalchemy import or_
    candidates = (await db.execute(select(User).where(
        User.business == s.business, User.is_active == True,
        User.role.in_(FIELD_ROLES),
        or_(User.bu == s.bu, s.bu == "Global", s.scope == "business"),
    ))).scalars().all()

    newly_detected = []
    for rep in candidates:
        current = await _compute_metric(db, rep, s.period, s.metric)
        if s.target_value and current < float(s.target_value):
            continue
        existing = (await db.execute(select(SchemeWinner).where(
            SchemeWinner.scheme_id == s.id, SchemeWinner.user_id == rep.id,
            SchemeWinner.period == s.period,
        ))).scalar_one_or_none()
        if existing:
            continue

        auto_approve = s.reward_type in ("points", "badge", "recognition")
        db.add(SchemeWinner(
            scheme_id=s.id, user_id=rep.id, period=s.period,
            achieved_value=current, target_value=s.target_value,
            reward_type=s.reward_type, reward_value=s.reward_value, reward_badge=s.reward_badge,
            status="approved" if auto_approve else "pending_hr",
            detected_at=datetime.utcnow(),
        ))

        if s.reward_type == "points" and s.reward_value:
            db.add(PointsLedger(user_id=rep.id, scheme_id=s.id, period=s.period,
                                points=int(s.reward_value), reason=f"Scheme achieved: {s.name}",
                                source="scheme_winner"))
        elif s.reward_type == "badge" and s.reward_badge and s.reward_badge in BADGES:
            existing_badge = (await db.execute(select(UserBadge).where(
                UserBadge.user_id == rep.id, UserBadge.badge_key == s.reward_badge,
                UserBadge.period == s.period,
            ))).scalar_one_or_none()
            if not existing_badge:
                db.add(UserBadge(user_id=rep.id, badge_key=s.reward_badge,
                                 badge_name=BADGES[s.reward_badge]["name"], period=s.period))

        newly_detected.append({"user_id": str(rep.id), "name": rep.name,
                               "value": current, "auto_approved": auto_approve})

    await db.commit()
    return {"scheme_id": scheme_id, "period": s.period, "newly_detected": newly_detected}


@router.get("/winners")
async def list_winners(status: Literal["pending_hr", "approved", "rejected", "all"] = "pending_hr",
                       db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_level(20))):
    """HR's review queue by default — cash winners awaiting sign-off before
    payout. Scoped the same way every other team-facing endpoint is
    (resolve_visible_user_ids; HR's scope='hr' already grants org-wide
    visibility, same as FGA audit)."""
    q = select(SchemeWinner)
    if status != "all":
        q = q.where(SchemeWinner.status == status)
    winners = (await db.execute(q.order_by(SchemeWinner.detected_at.desc()))).scalars().all()

    visible = await resolve_visible_user_ids(db, user)
    out = []
    for w in winners:
        if visible is not None and w.user_id not in visible:
            continue
        rep = (await db.execute(select(User).where(User.id == w.user_id))).scalar_one_or_none()
        sch = (await db.execute(select(IncentiveScheme).where(IncentiveScheme.id == w.scheme_id))).scalar_one_or_none()
        out.append(_serialize_winner(w, rep.name if rep else "Unknown", sch.name if sch else "Unknown scheme"))
    return out


@router.post("/winners/{winner_id}/review")
async def review_winner(winner_id: str, body: WinnerReviewIn,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """HR sign-off gate before a cash reward is treated as payable — same
    HR_ALLOWED shape as fga_approval.hr_review (HR, or manager-tier+, or
    super_admin)."""
    HR_ALLOWED = {"hr", "super_admin", "manager", "regional_manager", "bu_head",
                  "business_head", "practice_head", "ceo"}
    if user.role not in HR_ALLOWED:
        raise HTTPException(403, "Winner review requires HR or manager-level access")
    w = (await db.execute(select(SchemeWinner).where(SchemeWinner.id == uuid.UUID(winner_id)))).scalar_one_or_none()
    if not w:
        raise HTTPException(404, "Winner record not found")
    if w.status != "pending_hr":
        raise HTTPException(400, f"Cannot review: status is '{w.status}'")
    w.status = "approved" if body.action == "approve" else "rejected"
    w.hr_comment = body.comment
    w.hr_reviewed_by = user.id
    w.hr_reviewed_at = datetime.utcnow()
    await db.commit()
    return _serialize_winner(w)


@router.post("/winners/{winner_id}/mark-paid")
async def mark_winner_paid(winner_id: str, db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_level(20))):
    """Terminal step for an approved cash winner — confirms the money
    actually moved. Only valid from status='approved'."""
    w = (await db.execute(select(SchemeWinner).where(SchemeWinner.id == uuid.UUID(winner_id)))).scalar_one_or_none()
    if not w:
        raise HTTPException(404, "Winner record not found")
    if w.status != "approved":
        raise HTTPException(400, "Only an approved winner can be marked paid")
    w.paid = True
    w.paid_at = datetime.utcnow()
    await db.commit()
    return _serialize_winner(w)
