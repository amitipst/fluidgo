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
async def rep_analytics(user_id: str, scope: str = "auto",
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Returns per-day DSR rows with rigor scores.
    - Rep: their own rows.
    - Manager/BH viewing their own id with scope=auto: if they have no DSRs of
      their own (they don't log DSRs), automatically returns their TEAM's daily
      rows aggregated by date, so the Analytics charts aren't empty for them.
    - scope=self forces own-only; scope=team forces team aggregate."""
    from app.models import role_level
    is_manager = role_level(user.role) >= 20
    if not is_manager and str(user.id) != user_id:
        from fastapi import HTTPException
        raise HTTPException(403, "You can only view your own analytics")

    async def own_rows(uid):
        res = await db.execute(
            select(DSRDaily).where(DSRDaily.user_id == uuid.UUID(uid))
            .order_by(DSRDaily.date.asc())
        )
        return res.scalars().all()

    dsrs = await own_rows(user_id)

    # Manager viewing self with no personal DSRs → fall back to team aggregate
    want_team = scope == "team" or (
        scope == "auto" and is_manager and str(user.id) == user_id and len(dsrs) == 0
    )
    if want_team:
        from app.services.permission_service import resolve_visible_user_ids
        visible = await resolve_visible_user_ids(db, user)
        q = select(DSRDaily).order_by(DSRDaily.date.asc())
        if visible is not None:
            q = q.where(DSRDaily.user_id.in_(visible))
        team_dsrs = (await db.execute(q)).scalars().all()
        # Aggregate by date so the chart has one point per day (team totals)
        by_date: dict = {}
        for d in team_dsrs:
            key = d.date
            agg = by_date.setdefault(key, {
                "date": d.date, "status": "working",
                "calls": 0, "visits": 0, "followups": 0, "new_leads": 0, "proposals": 0,
                "_rigor_sum": 0, "_rigor_n": 0,
            })
            agg["calls"]     += d.calls
            agg["visits"]    += d.visits
            agg["followups"] += d.followups
            agg["new_leads"] += d.new_leads
            agg["proposals"] += d.proposals
            if d.status == "working":
                agg["_rigor_sum"] += calculate_rigor_score(d)
                agg["_rigor_n"]   += 1
        out = []
        for key in sorted(by_date.keys()):
            a = by_date[key]
            rigor = round(a["_rigor_sum"] / a["_rigor_n"]) if a["_rigor_n"] else 0
            out.append({
                "date": a["date"], "status": a["status"],
                "calls": a["calls"], "visits": a["visits"], "followups": a["followups"],
                "new_leads": a["new_leads"], "proposals": a["proposals"],
                "rigor_score": rigor, "rigor_label": rigor_label(rigor),
                "is_team_aggregate": True,
            })
        return out

    return [
        {**{c.name: getattr(d, c.name) for c in d.__table__.columns},
         "rigor_score": calculate_rigor_score(d),
         "rigor_label": rigor_label(calculate_rigor_score(d))}
        for d in dsrs
    ]

@router.get("/team")
async def team_analytics(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_role("manager", "regional_manager", "bu_head", "business_head", "inside_sales", "ceo", "super_admin"))):
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

    if user.role in ("manager", "regional_manager", "bu_head", "business_head", "ceo", "super_admin", "hr"):
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

@router.get("/my-revenue")
async def my_revenue(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """The CALLER's own revenue target vs achievement — visible to every role
    (a rep can see their own numbers). Revenue and Order Booking kept separate.
    Supports monthly ('2026-07'), quarterly ('2026-Q2') and yearly ('2026')."""
    today = date.today()
    p = period or f"{today.year}-{today.month:02d}"
    start, end = _period_bounds(p)

    # Won revenue in the period (this user only)
    deals = (await db.execute(
        select(PipelineDeal).where(PipelineDeal.user_id == user.id)
    )).scalars().all()
    won = [d for d in deals if d.stage == "closed_won"
           and d.closure_eta and start <= d.closure_eta <= end]
    won_revenue = sum(float(d.deal_value or 0) for d in won)

    # Targets: a target row's period may be monthly even when viewing a quarter,
    # so sum every target whose period-bounds fall inside the requested window.
    all_targets = (await db.execute(
        select(RevenueTarget).where(RevenueTarget.user_id == user.id)
    )).scalars().all()
    def in_window(t):
        try:
            ts, te = _period_bounds(t.period)
        except Exception:
            return False
        return ts >= start and te <= end
    scoped = [t for t in all_targets if in_window(t)]
    revenue_target = sum(float(t.target_amount) for t in scoped if t.target_type == "revenue")
    ob_target      = sum(float(t.target_amount) for t in scoped if t.target_type == "order_booking")

    achievement_pct = round(won_revenue / revenue_target * 100, 1) if revenue_target else 0.0

    return {
        "period": p,
        "revenue_achieved":     round(won_revenue, 2),
        "revenue_target":       round(revenue_target, 2),
        "order_booking_target": round(ob_target, 2),
        "achievement_pct":      achievement_pct,
        "gap":                  round(max(0.0, revenue_target - won_revenue), 2),
        "deals_won":            len(won),
        "has_target":           revenue_target > 0 or ob_target > 0,
    }

@router.get("/revenue")
async def revenue_analytics(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_role("manager", "regional_manager", "bu_head", "business_head", "ceo", "super_admin", "finance"))):
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
    # Revenue and Order Booking are SEPARATE measures — never sum them together.
    # The revenue KPIs (achievement, gap, coverage) compare won revenue against
    # the REVENUE target only. Order-booking target is returned separately.
    total_target        = sum(float(t.target_amount) for t in targets if t.target_type == "revenue")
    total_ob_target     = sum(float(t.target_amount) for t in targets if t.target_type == "order_booking")

    return {
        "period": p,
        "revenue":                   round(total_revenue, 2),
        "target":                    round(total_target, 2),
        "order_booking_target":      round(total_ob_target, 2),
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
    target_type: str = "revenue"   # revenue | order_booking

@router.post("/revenue/targets")
async def set_revenue_target(body: TargetIn, db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_role(
                                 "business_head", "coo", "ceo", "super_admin"
                             ))):
    """Set/update a revenue OR order-booking target for a user.
    Restricted to Business Head / COO / CEO (strategic targets are not set
    at manager level). target_type: 'revenue' | 'order_booking'."""
    from app.services.permission_service import can_user_edit_target
    if body.target_type not in ("revenue", "order_booking"):
        from fastapi import HTTPException
        raise HTTPException(400, "target_type must be 'revenue' or 'order_booking'")
    if not await can_user_edit_target(db, user, body.user_id):
        from fastapi import HTTPException
        raise HTTPException(403, "You cannot set targets for users outside your scope")

    existing = (await db.execute(
        select(RevenueTarget).where(
            RevenueTarget.user_id == uuid.UUID(body.user_id),
            RevenueTarget.period == body.period,
            RevenueTarget.target_type == body.target_type
        )
    )).scalar_one_or_none()
    if existing:
        existing.target_amount = body.target_amount
    else:
        db.add(RevenueTarget(
            user_id=uuid.UUID(body.user_id),
            period=body.period,
            target_type=body.target_type,
            target_amount=body.target_amount
        ))
    await db.commit()
    return {"user_id": body.user_id, "period": body.period,
            "target_type": body.target_type,
            "target_amount": body.target_amount, "updated_by": user.email}

@router.get("/revenue/targets")
async def list_revenue_targets(
    period: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(
        "manager", "regional_manager", "bu_head", "business_head", "coo", "ceo", "super_admin", "hr", "finance"
    ))
):
    """List both revenue and order-booking targets for the caller's visible
    users in a given period (default: current month)."""
    from app.services.permission_service import resolve_visible_user_ids
    today = date.today()
    p = period or f"{today.year}-{today.month:02d}"
    visible = await resolve_visible_user_ids(db, user)
    q = select(RevenueTarget).where(RevenueTarget.period == p)
    if visible is not None:
        q = q.where(RevenueTarget.user_id.in_(visible))
    rows = (await db.execute(q)).scalars().all()
    # Group per user so the UI can show revenue + order_booking side by side
    out: dict = {}
    for r in rows:
        uid = str(r.user_id)
        out.setdefault(uid, {"user_id": uid, "revenue": None, "order_booking": None})
        out[uid][r.target_type] = float(r.target_amount)
    return list(out.values())


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
        # Revenue vs Order Booking are separate — the revenue achievement KPI
        # must compare against the REVENUE target only, never the sum of both.
        total_target    = sum(float(t.target_amount) for t in targets if t.target_type == "revenue")
        total_ob_target = sum(float(t.target_amount) for t in targets if t.target_type == "order_booking")
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
            "order_booking_target": round(total_ob_target, 2),
            "achievement_pct": round((total_revenue/total_target*100) if total_target else 0, 1),
            "deals_won":      len(deals),
            "dsr_days":       dsr_days,
            "working_days":   working_days,
        }

    def delta(curr_val, prev_val, is_future: bool = False) -> dict:
        if is_future:
            return {"value": curr_val, "change": None, "trend": "future"}
        if prev_val == 0:
            return {"value": curr_val, "change": None, "trend": "new"}
        chg = round((curr_val - prev_val) / prev_val * 100, 1)
        return {
            "value":  curr_val,
            "change": chg,
            "trend":  "up" if chg > 0 else "down" if chg < 0 else "flat",
        }

    # A period that hasn't started yet shouldn't show misleading "-100%" deltas
    is_future_period = curr_start > date.today()

    curr_kpis = await period_kpis(curr_start, curr_end)
    prev_kpis = await period_kpis(prev_start, prev_end) if prev_start else {}

    # MoM comparison (monthly mode only)
    mom_kpis = {}
    if mode == "monthly" and parsed.get("mom"):
        mom_start, mom_end = parsed["mom"]
        mom_kpis = await period_kpis(mom_start, mom_end)

    kpi_keys = ["calls", "visits", "followups", "leads", "proposals",
                "avg_rigor", "revenue", "target", "order_booking_target",
                "achievement_pct", "deals_won"]
    comparison = {}
    for k in kpi_keys:
        comparison[k] = {
            "current":  curr_kpis.get(k, 0),
            "yoy":      delta(curr_kpis.get(k, 0), prev_kpis.get(k, 0), is_future_period) if prev_kpis else None,
            "mom":      delta(curr_kpis.get(k, 0), mom_kpis.get(k, 0), is_future_period)  if mom_kpis  else None,
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
        "is_future":  is_future_period,
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
    mode: str = "monthly",          # monthly | quarterly | yearly
    fy: Optional[int] = None,       # required for quarterly/yearly (e.g. 2026 = FY2026-27)
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("manager", "regional_manager", "bu_head", "business_head", "coo", "ceo", "super_admin"))
):
    """Returns all team members with BOTH their revenue and order-booking
    targets. Used by the Target Editor UI.

    - mode=monthly (default): same as before, exact period match e.g. "2026-07".
    - mode=quarterly: returns q1..q4 (ACTUAL monthly-summed values, always in
      sync with what Analytics/Performance shows) plus fy_total, for the given fy.
    - mode=yearly: same shape as quarterly (full FY grid) so one screen can
      drive both the single-quarter editor and the FY rollover wizard.
    """
    from app.services.permission_service import resolve_visible_user_ids
    from app.services.period_service import months_in_quarter, get_india_fy
    today = date.today()

    visible_ids = await resolve_visible_user_ids(db, user)
    q = select(User).where(
        User.is_active == True,
        User.role.in_(["rep", "inside_sales", "pre_sales", "manager"])
    )
    if visible_ids is not None:
        q = q.where(User.id.in_(visible_ids))
    team = (await db.execute(q)).scalars().all()
    team_ids = [u.id for u in team]

    if mode in ("quarterly", "yearly"):
        fy_yr = fy or get_india_fy(today)
        # Pull every monthly target row for this FY in one query, then bucket
        # it into quarters in Python — always reflects the true monthly sum,
        # so the editor can never drift from what Analytics displays.
        fy_periods = [f"{y}-{m:02d}" for q_ in (1, 2, 3, 4) for (y, m) in months_in_quarter(q_, fy_yr)]
        rows = (await db.execute(
            select(RevenueTarget).where(
                RevenueTarget.user_id.in_(team_ids),
                RevenueTarget.period.in_(fy_periods)
            )
        )).scalars().all()
        month_to_q = {}
        for q_ in (1, 2, 3, 4):
            for (y, m) in months_in_quarter(q_, fy_yr):
                month_to_q[f"{y}-{m:02d}"] = q_

        # {user_id: {revenue: {1:x,2:x,3:x,4:x}, order_booking: {...}}}
        buckets: dict = {}
        for r in rows:
            uid = str(r.user_id)
            buckets.setdefault(uid, {"revenue": {1: 0, 2: 0, 3: 0, 4: 0},
                                      "order_booking": {1: 0, 2: 0, 3: 0, 4: 0}})
            q_num = month_to_q.get(r.period)
            if q_num:
                buckets[uid][r.target_type][q_num] += float(r.target_amount)

        def member_row(u):
            b = buckets.get(str(u.id), {"revenue": {1: 0, 2: 0, 3: 0, 4: 0},
                                          "order_booking": {1: 0, 2: 0, 3: 0, 4: 0}})
            return {
                "user_id": str(u.id), "name": u.name, "email": u.email,
                "role": u.role, "region": getattr(u, "region", None) or u.bu,
                "revenue":       {"q1": b["revenue"][1], "q2": b["revenue"][2],
                                   "q3": b["revenue"][3], "q4": b["revenue"][4],
                                   "fy_total": sum(b["revenue"].values())},
                "order_booking": {"q1": b["order_booking"][1], "q2": b["order_booking"][2],
                                   "q3": b["order_booking"][3], "q4": b["order_booking"][4],
                                   "fy_total": sum(b["order_booking"].values())},
            }

        return {
            "mode": mode, "fy": fy_yr, "fy_label": f"FY {fy_yr}-{str(fy_yr+1)[2:]}",
            "members": [member_row(u) for u in sorted(team, key=lambda x: (x.region or "", x.name))]
        }

    # ── monthly mode (original behaviour, unchanged) ──────────────────────
    p = period or f"{today.year}-{today.month:02d}"
    targets: dict = {}
    for t in (await db.execute(
        select(RevenueTarget).where(
            RevenueTarget.user_id.in_(team_ids),
            RevenueTarget.period == p
        )
    )).scalars().all():
        uid = str(t.user_id)
        targets.setdefault(uid, {})
        targets[uid][t.target_type] = float(t.target_amount)

    return {
        "mode": "monthly",
        "period": p,
        "members": [
            {
                "user_id":       str(u.id),
                "name":          u.name,
                "email":         u.email,
                "role":          u.role,
                "region":        getattr(u, "region", None) or u.bu,
                "target":        targets.get(str(u.id), {}).get("revenue", 0),        # revenue (back-compat key)
                "revenue":       targets.get(str(u.id), {}).get("revenue", 0),
                "order_booking": targets.get(str(u.id), {}).get("order_booking", 0),
            }
            for u in sorted(team, key=lambda x: (x.region or "", x.name))
        ]
    }


class QuarterlyTargetRow(BaseModel):
    user_id: str
    q1: float = 0
    q2: float = 0
    q3: float = 0
    q4: float = 0

class QuarterlyTargetsBulkIn(BaseModel):
    fy: int                              # e.g. 2026 for FY 2026-27
    target_type: str = "revenue"         # revenue | order_booking
    rows: list[QuarterlyTargetRow]
    quarters: Optional[list[int]] = None # which quarters to touch; default all 4


@router.post("/revenue/targets/quarterly")
async def set_quarterly_targets_bulk(
    body: QuarterlyTargetsBulkIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("business_head", "coo", "ceo", "super_admin"))
):
    """Set Q1-Q4 targets for any number of team members in ONE save.
    Each quarter total is split evenly across its 3 months and written as
    normal monthly revenue_targets rows — the SAME rows Analytics/Performance
    already sums over, so there is never a separate 'quarterly' or 'yearly'
    literal period key to drift out of sync.

    Pass `quarters` to only touch specific quarters (e.g. mid-year top-up);
    omit it to set/replace the full FY in one call (typical FY rollover use)."""
    from app.services.permission_service import can_user_edit_target
    from app.services.period_service import months_in_quarter
    from fastapi import HTTPException

    if body.target_type not in ("revenue", "order_booking"):
        raise HTTPException(400, "target_type must be 'revenue' or 'order_booking'")
    quarters_to_set = body.quarters or [1, 2, 3, 4]
    for q_num in quarters_to_set:
        if q_num not in (1, 2, 3, 4):
            raise HTTPException(400, "quarters must be within 1-4")

    updated_users = []
    for row in body.rows:
        if not await can_user_edit_target(db, user, row.user_id):
            raise HTTPException(403, f"You cannot set targets for user {row.user_id}")
        quarter_amounts = {1: row.q1, 2: row.q2, 3: row.q3, 4: row.q4}
        uid = uuid.UUID(row.user_id)
        for q_num in quarters_to_set:
            months = months_in_quarter(q_num, body.fy)
            per_month = round(quarter_amounts[q_num] / len(months), 2) if months else 0
            for (yr, mo) in months:
                period_str = f"{yr}-{mo:02d}"
                existing = (await db.execute(
                    select(RevenueTarget).where(
                        RevenueTarget.user_id == uid,
                        RevenueTarget.period == period_str,
                        RevenueTarget.target_type == body.target_type
                    )
                )).scalar_one_or_none()
                if existing:
                    existing.target_amount = per_month
                else:
                    db.add(RevenueTarget(
                        user_id=uid, period=period_str,
                        target_type=body.target_type, target_amount=per_month
                    ))
        updated_users.append(row.user_id)

    await db.commit()
    fy_totals = {row.user_id: round(row.q1 + row.q2 + row.q3 + row.q4, 2) for row in body.rows}
    return {
        "fy": body.fy, "target_type": body.target_type,
        "quarters_updated": quarters_to_set,
        "users_updated": len(updated_users),
        "fy_totals": fy_totals,
        "updated_by": user.email,
    }


@router.get("/revenue/targets/rollover-preview")
async def rollover_preview(
    fy: int,                             # target FY to pre-fill, e.g. 2027 for FY2027-28
    growth_pct: float = 15.0,
    target_type: str = "revenue",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("business_head", "coo", "ceo", "super_admin"))
):
    """Suggests CFY quarterly targets by taking each member's PFY (fy-1)
    quarterly actual-target totals and applying growth_pct uplift.
    Pure preview — writes nothing. The BU Head hand-tunes then saves via
    POST /revenue/targets/quarterly."""
    from app.services.permission_service import resolve_visible_user_ids
    from app.services.period_service import months_in_quarter

    visible_ids = await resolve_visible_user_ids(db, user)
    q = select(User).where(
        User.is_active == True,
        User.role.in_(["rep", "inside_sales", "pre_sales", "manager"])
    )
    if visible_ids is not None:
        q = q.where(User.id.in_(visible_ids))
    team = (await db.execute(q)).scalars().all()
    team_ids = [u.id for u in team]

    pfy = fy - 1
    pfy_periods = [f"{y}-{m:02d}" for q_ in (1, 2, 3, 4) for (y, m) in months_in_quarter(q_, pfy)]
    month_to_q = {}
    for q_ in (1, 2, 3, 4):
        for (y, m) in months_in_quarter(q_, pfy):
            month_to_q[f"{y}-{m:02d}"] = q_

    rows = (await db.execute(
        select(RevenueTarget).where(
            RevenueTarget.user_id.in_(team_ids),
            RevenueTarget.period.in_(pfy_periods),
            RevenueTarget.target_type == target_type
        )
    )).scalars().all()

    pfy_totals: dict = {}
    for r in rows:
        uid = str(r.user_id)
        pfy_totals.setdefault(uid, {1: 0, 2: 0, 3: 0, 4: 0})
        q_num = month_to_q.get(r.period)
        if q_num:
            pfy_totals[uid][q_num] += float(r.target_amount)

    mult = 1 + (growth_pct / 100)
    suggestions = []
    for u in sorted(team, key=lambda x: (x.region or "", x.name)):
        pfy_q = pfy_totals.get(str(u.id), {1: 0, 2: 0, 3: 0, 4: 0})
        suggested = {k: round(v * mult, 2) for k, v in pfy_q.items()}
        suggestions.append({
            "user_id": str(u.id), "name": u.name, "region": getattr(u, "region", None) or u.bu,
            "pfy_q1": pfy_q[1], "pfy_q2": pfy_q[2], "pfy_q3": pfy_q[3], "pfy_q4": pfy_q[4],
            "pfy_total": round(sum(pfy_q.values()), 2),
            "q1": suggested[1], "q2": suggested[2], "q3": suggested[3], "q4": suggested[4],
            "fy_total": round(sum(suggested.values()), 2),
        })

    return {
        "fy": fy, "pfy": pfy, "growth_pct": growth_pct, "target_type": target_type,
        "members": suggestions,
    }


@router.get("/funnel")
async def funnel_analytics(db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """Conversion funnel: Meetings → Leads → Deals → Won, with conversion rates.
    Scoped to the caller's visible users (own for reps, team for managers).
    This is the business-insight view a Business Head actually wants."""
    from app.models import Meeting, Lead, role_level
    from sqlalchemy import func

    # Scope: managers see their team, reps see themselves
    if role_level(user.role) >= 20:
        visible = await resolve_visible_user_ids(db, user)
    else:
        visible = [user.id]

    def _scoped(q, col):
        return q.where(col.in_(visible)) if visible is not None else q

    meetings_total = (await db.execute(_scoped(
        select(func.count(Meeting.id)), Meeting.user_id))).scalar() or 0
    meetings_converted = (await db.execute(_scoped(
        select(func.count(Meeting.id)).where(Meeting.converted_to_lead_id.isnot(None)),
        Meeting.user_id))).scalar() or 0
    leads_total = (await db.execute(_scoped(
        select(func.count(Lead.id)), Lead.user_id))).scalar() or 0
    leads_converted = (await db.execute(_scoped(
        select(func.count(Lead.id)).where(Lead.converted_to_deal_id.isnot(None)),
        Lead.user_id))).scalar() or 0
    deals_total = (await db.execute(_scoped(
        select(func.count(PipelineDeal.id)), PipelineDeal.user_id))).scalar() or 0
    deals_won = (await db.execute(_scoped(
        select(func.count(PipelineDeal.id)).where(PipelineDeal.stage == "closed_won"),
        PipelineDeal.user_id))).scalar() or 0

    # Value at each pipeline stage (open vs won)
    open_value = (await db.execute(_scoped(
        select(func.coalesce(func.sum(PipelineDeal.deal_value), 0)).where(
            PipelineDeal.stage.notin_(["closed_won", "closed_lost"])),
        PipelineDeal.user_id))).scalar() or 0
    won_value = (await db.execute(_scoped(
        select(func.coalesce(func.sum(PipelineDeal.deal_value), 0)).where(
            PipelineDeal.stage == "closed_won"),
        PipelineDeal.user_id))).scalar() or 0

    def pct(n, d): return round(100 * n / d) if d else 0

    return {
        "is_team": role_level(user.role) >= 20,
        "stages": [
            {"label": "Meetings",  "count": meetings_total,   "value": None},
            {"label": "Leads",     "count": leads_total,      "value": None,
             "conv_from_prev": pct(leads_total, meetings_total)},
            {"label": "Deals",     "count": deals_total,      "value": float(open_value),
             "conv_from_prev": pct(deals_total, leads_total)},
            {"label": "Won",       "count": deals_won,        "value": float(won_value),
             "conv_from_prev": pct(deals_won, deals_total)},
        ],
        "overall_conversion": pct(deals_won, meetings_total),
        "open_pipeline_value": float(open_value),
        "won_value": float(won_value),
    }
