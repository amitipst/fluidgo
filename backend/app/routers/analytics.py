from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date
from typing import Optional
import uuid
from app.database import get_db
from app.models import User, DSRDaily, PipelineDeal, RevenueTarget
from app.services.deps import get_current_user, require_role
from app.services.rigor_service import calculate_rigor_score, calculate_avg_rigor, rigor_label
from app.services.permission_service import resolve_visible_user_ids
from app.services.scoring_engine import _period_bounds

router = APIRouter()

@router.get("/rep/{user_id}")
async def rep_analytics(user_id: str, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Returns per-day DSR rows for a single rep, with rigor scores.
    BU Head / Manager can query any rep_id; a Rep can only query their own."""
    if user.role not in ("manager", "bu_head") and str(user.id) != user_id:
        from fastapi import HTTPException
        raise HTTPException(403, "You can only view your own analytics")
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
                         user: User = Depends(require_role("manager", "bu_head", "business_head", "inside_sales", "ceo", "super_admin"))):
    """Team performance matrix — scoped by role/BU automatically.
    Exited reps (is_active=False) excluded by default; include_inactive=true shows them."""
    # Use permission_service for consistent scope resolution across all roles
    visible_ids = await resolve_visible_user_ids(db, user)

    query = select(User)
    if not include_inactive:
        query = query.where(User.is_active == True)
    if visible_ids is not None:
        query = query.where(User.id.in_(visible_ids))

    users_result = await db.execute(query)
    users = users_result.scalars().all()

    out = []
    for u in users:
        dsrs_result = await db.execute(
            select(DSRDaily).where(DSRDaily.user_id == u.id)
        )
        dsrs = dsrs_result.scalars().all()
        working = [d for d in dsrs if d.status == "working"]
        avg_rigor = calculate_avg_rigor(dsrs)  # ← uses fixed formula, excludes exempt days

        out.append({
            "user_id": str(u.id), "name": u.name, "role": u.role, "is_active": u.is_active,
            "bu": u.bu,
            "total_days": len(dsrs), "working_days": len(working),
            "total_calls":     sum(d.calls for d in dsrs),
            "total_visits":    sum(d.visits for d in dsrs),
            "total_followups": sum(d.followups for d in dsrs),
            "total_leads":     sum(d.new_leads for d in dsrs),
            "total_proposals": sum(d.proposals for d in dsrs),
            "avg_rigor":       avg_rigor,
            "rigor_label":     rigor_label(int(avg_rigor))
        })
    return sorted(out, key=lambda x: x["avg_rigor"], reverse=True)

@router.get("/dashboard")
async def bu_dashboard(month: Optional[str] = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Role-aware dashboard KPIs.
    - Rep/Inside Sales: their own totals for the selected month (default: current month)
    - Manager/BU Head: their BU's aggregated totals for the selected month
    month param format: YYYY-MM (e.g. 2026-05)"""
    today = date.today()
    if month:
        year_s, mon_s = month.split("-")
        month_start = date(int(year_s), int(mon_s), 1)
    else:
        month_start = today.replace(day=1)

    # Calculate month end
    from calendar import monthrange
    if month:
        year_s, mon_s = month.split("-")
        yr, mo = int(year_s), int(mon_s)
    else:
        yr, mo = today.year, today.month
    month_end = date(yr, mo, monthrange(yr, mo)[1])

    if user.role in ("manager", "bu_head", "business_head", "ceo", "super_admin", "hr"):
        # Use permission_service — handles business_head (all regions), manager (team), etc.
        visible_ids = await resolve_visible_user_ids(db, user)
        q = select(User).where(User.is_active == True)
        if visible_ids is not None:
            q = q.where(User.id.in_(visible_ids))
        bu_users = (await db.execute(q)).scalars().all()
        user_ids = [u.id for u in bu_users]
        dsrs = (await db.execute(
            select(DSRDaily).where(
                DSRDaily.user_id.in_(user_ids),
                DSRDaily.date >= month_start,
                DSRDaily.date <= month_end
            )
        )).scalars().all()
        pending_today = len([u for u in bu_users
                             if u.id not in {d.user_id for d in dsrs if d.date == today}]) \
                        if not month else 0
    else:
        dsrs = (await db.execute(
            select(DSRDaily).where(
                DSRDaily.user_id == user.id,
                DSRDaily.date >= month_start,
                DSRDaily.date <= month_end
            )
        )).scalars().all()
        pending_today = 0

    working = [d for d in dsrs if d.status == "working"]
    return {
        "period": f"{yr}-{mo:02d}",
        "total_calls":     sum(d.calls for d in dsrs),
        "total_visits":    sum(d.visits for d in dsrs),
        "total_followups": sum(d.followups for d in dsrs),
        "total_leads":     sum(d.new_leads for d in dsrs),
        "total_proposals": sum(d.proposals for d in dsrs),
        "avg_rigor":       calculate_avg_rigor(dsrs),
        "working_days":    len(working),
        "total_days":      len(dsrs),
        "pending_today":   pending_today,
    }

@router.get("/revenue")
async def revenue_analytics(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_role("manager", "bu_head", "business_head", "ceo", "super_admin", "finance"))):
    """Revenue Intelligence — scoped by permission_service (works for all roles)."""
    today = date.today()
    p = period or f"{today.year}-{today.month:02d}"
    start, end = _period_bounds(p)

    # Use permission_service — handles business_head (all regions), manager (team), etc.
    visible_ids = await resolve_visible_user_ids(db, user)
    q = select(User).where(User.is_active == True)
    if visible_ids is not None:
        q = q.where(User.id.in_(visible_ids))
    bu_users = (await db.execute(q)).scalars().all()
    bu_user_ids = [u.id for u in bu_users]

    deals = (await db.execute(
        select(PipelineDeal).where(PipelineDeal.user_id.in_(bu_user_ids))
    )).scalars().all()

    won       = [d for d in deals if d.stage == "closed_won"
                 and d.closure_eta and start <= d.closure_eta <= end]
    lost      = [d for d in deals if d.stage == "closed_lost"]
    open_deals= [d for d in deals if d.stage not in ("closed_won", "closed_lost")]

    total_revenue  = sum(float(d.deal_value or 0) for d in won)
    pipeline_value = sum(float(d.deal_value or 0) for d in open_deals)
    win_pct        = (len(won) / (len(won) + len(lost)) * 100) if (won or lost) else 0.0
    avg_deal_size  = (total_revenue / len(won)) if won else 0.0

    targets = (await db.execute(
        select(RevenueTarget).where(
            RevenueTarget.user_id.in_(bu_user_ids),
            RevenueTarget.period == p
        )
    )).scalars().all()
    total_target = sum(float(t.target_amount) for t in targets)

    return {
        "period": p,
        "revenue":                   round(total_revenue, 2),
        "target":                    round(total_target, 2),
        "gap":                       round(total_target - total_revenue, 2),
        "target_achievement_pct":    round((total_revenue / total_target * 100) if total_target else 0, 1),
        "pipeline_coverage_ratio":   round((pipeline_value / total_target) if total_target else 0, 2),
        "win_pct":                   round(win_pct, 1),
        "avg_deal_size":             round(avg_deal_size, 2),
        "open_deal_count":           len(open_deals),
        "pipeline_value":            round(pipeline_value, 2),
        "won_count":                 len(won),
    }

class TargetIn(BaseModel):
    user_id: str
    period: str
    target_amount: float

@router.post("/revenue/targets")
async def set_revenue_target(body: TargetIn, db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_role(
                                 "manager", "bu_head", "business_head", "ceo", "super_admin"
                             ))):
    """Set/update revenue target for a user.
    BU Head and above can set targets for anyone in their scope.
    Manager can only set targets for their direct reports."""
    from app.services.permission_service import can_user_edit_target
    if not await can_user_edit_target(db, user, body.user_id):
        from fastapi import HTTPException
        raise HTTPException(403, "You cannot set targets for users outside your scope")

    existing = (await db.execute(
        select(RevenueTarget).where(
            RevenueTarget.user_id == uuid.UUID(body.user_id),
            RevenueTarget.period == body.period
        )
    )).scalar_one_or_none()
    if existing:
        existing.target_amount = body.target_amount
    else:
        db.add(RevenueTarget(
            user_id=uuid.UUID(body.user_id),
            period=body.period,
            target_amount=body.target_amount
        ))
    await db.commit()
    return {"user_id": body.user_id, "period": body.period,
            "target_amount": body.target_amount, "updated_by": user.email}


@router.get("/regional")
async def regional_performance(
    period: Optional[str] = None,
    region: Optional[str] = None,   # drill into a specific region
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Regional performance dashboard — business_head and above only.
    Returns performance KPIs sliced by India region.
    Optional ?region=India+-+West to drill into one region."""
    from app.models import role_level
    from app.services.permission_service import get_region_summary, resolve_visible_user_ids

    if role_level(user.role) < 20:
        from fastapi import HTTPException
        raise HTTPException(403, "Regional analytics requires manager role or above")

    today = date.today()
    p = period or f"{today.year}-{today.month:02d}"

    # Business head / CEO get full regional breakdown
    if role_level(user.role) >= 40:
        regions = await get_region_summary(db, user, p)
        if region:
            regions = [r for r in regions if r["region"] == region]
        return {
            "period": p,
            "scope": "all_regions",
            "business": user.business,
            "regions": regions,
            "total_regions": len(regions),
        }

    # Manager / BU Head — return their own region summary
    return {
        "period": p,
        "scope": "own_region",
        "region": user.region or user.bu,
        "business": user.business,
        "regions": [],   # drill-down not available at this level
    }


@router.get("/performance")
async def performance_comparison(
    mode: str = "monthly",           # weekly | monthly | quarterly | yearly
    period: Optional[str] = None,   # "2026-05" | "2026-Q2" | "2026" | "2026-W28"
    region: Optional[str] = None,   # optional region filter for business_head
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Multi-period performance comparison with CFY vs PFY.

    Returns current + previous period KPIs with delta/trend.
    Supports: weekly, monthly, quarterly, yearly.

    India FY: April 1 → March 31
    Quarters: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
    """
    from app.models import role_level
    from app.services.period_service import parse_period
    from app.services.permission_service import resolve_visible_user_ids

    if role_level(user.role) < 10:
        from fastapi import HTTPException
        raise HTTPException(403, "Authentication required")

    parsed = parse_period(period, mode)
    curr_start, curr_end = parsed["current"]
    prev_start, prev_end = parsed.get("previous") or (None, None)

    # Resolve visible users
    visible_ids = await resolve_visible_user_ids(db, user, region_filter=region)
    q_users = select(User).where(User.is_active == True)
    if visible_ids is not None:
        q_users = q_users.where(User.id.in_(visible_ids))
    team = (await db.execute(q_users)).scalars().all()
    team_ids = [u.id for u in team]

    async def period_kpis(start: date, end: date) -> dict:
        if not start:
            return {}
        dsrs = (await db.execute(
            select(DSRDaily).where(
                DSRDaily.user_id.in_(team_ids),
                DSRDaily.date >= start,
                DSRDaily.date <= end,
            )
        )).scalars().all()
        deals = (await db.execute(
            select(PipelineDeal).where(
                PipelineDeal.user_id.in_(team_ids),
                PipelineDeal.closure_eta >= start,
                PipelineDeal.closure_eta <= end,
                PipelineDeal.stage == "closed_won"
            )
        )).scalars().all()
        targets = (await db.execute(
            select(RevenueTarget).where(
                RevenueTarget.user_id.in_(team_ids),
                RevenueTarget.period.between(
                    f"{start.year}-{start.month:02d}",
                    f"{end.year}-{end.month:02d}"
                )
            )
        )).scalars().all()
        from app.services.rigor_service import calculate_avg_rigor
        total_calls     = sum(d.calls for d in dsrs)
        total_visits    = sum(d.visits for d in dsrs)
        total_followups = sum(d.followups for d in dsrs)
        total_leads     = sum(d.new_leads for d in dsrs)
        total_proposals = sum(d.proposals for d in dsrs)
        avg_rigor       = calculate_avg_rigor(dsrs)
        total_revenue   = sum(float(d.deal_value or 0) for d in deals)
        total_target    = sum(float(t.target_amount) for t in targets)
        dsr_days        = len(dsrs)
        working_days    = len([d for d in dsrs if d.status == "working"])
        return {
            "calls":          total_calls,
            "visits":         total_visits,
            "followups":      total_followups,
            "leads":          total_leads,
            "proposals":      total_proposals,
            "avg_rigor":      round(avg_rigor, 1),
            "revenue":        round(total_revenue, 2),
            "target":         round(total_target, 2),
            "achievement_pct": round((total_revenue/total_target*100) if total_target else 0, 1),
            "deals_won":      len(deals),
            "dsr_days":       dsr_days,
            "working_days":   working_days,
        }

    def delta(curr_val, prev_val) -> dict:
        if prev_val == 0:
            return {"value": curr_val, "change": None, "trend": "new"}
        chg = round((curr_val - prev_val) / prev_val * 100, 1)
        return {
            "value":  curr_val,
            "change": chg,
            "trend":  "up" if chg > 0 else "down" if chg < 0 else "flat",
        }

    curr_kpis = await period_kpis(curr_start, curr_end)
    prev_kpis = await period_kpis(prev_start, prev_end) if prev_start else {}

    # MoM comparison (monthly mode only)
    mom_kpis = {}
    if mode == "monthly" and parsed.get("mom"):
        mom_start, mom_end = parsed["mom"]
        mom_kpis = await period_kpis(mom_start, mom_end)

    kpi_keys = ["calls", "visits", "followups", "leads", "proposals",
                "avg_rigor", "revenue", "target", "achievement_pct", "deals_won"]
    comparison = {}
    for k in kpi_keys:
        comparison[k] = {
            "current":  curr_kpis.get(k, 0),
            "yoy":      delta(curr_kpis.get(k, 0), prev_kpis.get(k, 0)) if prev_kpis else None,
            "mom":      delta(curr_kpis.get(k, 0), mom_kpis.get(k, 0))  if mom_kpis  else None,
        }

    return {
        "mode":       mode,
        "period":     parsed.get("label"),
        "prev_period": parsed.get("prev_label"),
        "mom_period": parsed.get("mom_label"),
        "quarter":    parsed.get("quarter"),
        "fy_start":   parsed.get("fy_start"),
        "region":     region,
        "team_size":  len(team),
        "kpis":       comparison,
        "raw": {
            "current":  curr_kpis,
            "previous": prev_kpis,
            "mom":      mom_kpis,
        }
    }


@router.get("/revenue/team-targets")
async def get_team_targets(
    period: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("manager", "bu_head", "business_head", "ceo", "super_admin"))
):
    """Returns all team members with their revenue targets for a period.
    Used by the Target Editor UI — business_head sees all, manager sees own team."""
    from app.services.permission_service import resolve_visible_user_ids
    today = date.today()
    p = period or f"{today.year}-{today.month:02d}"

    visible_ids = await resolve_visible_user_ids(db, user)
    q = select(User).where(
        User.is_active == True,
        User.role.in_(["rep", "inside_sales", "pre_sales", "manager"])
    )
    if visible_ids is not None:
        q = q.where(User.id.in_(visible_ids))
    team = (await db.execute(q)).scalars().all()

    targets = {
        str(t.user_id): float(t.target_amount)
        for t in (await db.execute(
            select(RevenueTarget).where(
                RevenueTarget.user_id.in_([u.id for u in team]),
                RevenueTarget.period == p
            )
        )).scalars().all()
    }

    return {
        "period": p,
        "members": [
            {
                "user_id":   str(u.id),
                "name":      u.name,
                "email":     u.email,
                "role":      u.role,
                "region":    getattr(u, "region", None) or u.bu,
                "target":    targets.get(str(u.id), 0),
            }
            for u in sorted(team, key=lambda x: (x.region or "", x.name))
        ]
    }
