"""Reports module (v1) — added 2026-10-23, Amit: "there is no report section
still". Scoped before building (see claude/README.md's v1.4.4 section) as a
CATALOG, not a new reporting engine: a single front door for report/export
functionality that was scattered across Team/Analytics/FGA, plus three new
reports the recent revenue-fix and rigor-trend work unlock. Every endpoint
here reuses an existing, already-tested service/computation rather than
re-implementing one — see each endpoint's docstring for exactly what it
reuses, per the Constitution's "can this be reused?" gate.

Gated to manager+ (require_any_manager — role_level >= 20, or hr/finance)
to match the existing export buttons on Team/Analytics/FGA, which this
module's four "relink" entries point straight back at rather than
duplicating. Not gated by a hardcoded role-name list (the bug class CRM
Admin's onboarding caught in v1.4.2 — a new scope="all" role missing from a
hand-maintained list) — a level check keeps a future role included by
construction."""
import csv
import io
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.booking_date import won_date_col, won_date_of
from app.database import get_db
from app.services.export_guard import export_guard
from app.models import User, PipelineDeal, DSRDaily, RevenueTarget, role_level
from app.services.deps import get_current_user, deny_governance, require_any_manager
from app.services.permission_service import resolve_visible_user_ids
from app.services.pipeline_sheet_service import amounts as _amounts
from app.services.rigor_service import aggregate_rigor_breakdown
from app.services.scoring_engine import _period_bounds

router = APIRouter()


def _deal_revenue(d) -> dict:
    """Full ARR/one-time/total breakdown — not just the total — so these
    reports can answer Amit's "ARR and One time option" ask directly rather
    than collapsing it back to one number. Same amounts() fallback as every
    other 2026-10-23 revenue fix (analytics.py, scoring_engine.py,
    incentives.py, pipeline.py)."""
    return _amounts(d.recurring_revenue, d.one_time_revenue, d.deal_value)


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        raise HTTPException(404, "Nothing to export for this selection.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


async def _visible_reps(db: AsyncSession, user: User) -> list[User]:
    visible_ids = await resolve_visible_user_ids(db, user)
    q = select(User).where(User.is_active == True)
    if visible_ids is not None:
        q = q.where(User.id.in_(visible_ids))
    return list((await db.execute(q)).scalars().all())


@router.get("/revenue-vs-target.csv", dependencies=[Depends(export_guard("Revenue vs target CSV"))])
async def export_revenue_vs_target(
    granularity: str = "monthly", periods: int = 6,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_any_manager),
):
    """Per-rep revenue vs target, several periods at once (Amit: "update
    actual revenue data on weekly basis... ARR and One time option which can
    be calculated against target vs achievement"). `monthly` reuses the exact
    per-rep/per-period computation `/analytics/performance/export` already
    does for one period — extended here to `periods` consecutive months so
    it reads as a trend, not a snapshot.

    `weekly` is honest about what the data actually supports: RevenueTarget
    only has monthly/quarterly/yearly periods (see scoring_engine.py's
    _period_bounds) — there is no weekly target to compare against, and
    fabricating a prorated one would be a guess dressed up as data. So
    `weekly` shows actual revenue booked per ISO week within the current
    month, with no target column — a cadence view, not an achievement view."""
    deny_governance(user)
    if granularity not in ("weekly", "monthly"):
        raise HTTPException(400, "granularity must be 'weekly' or 'monthly'")
    reps = await _visible_reps(db, user)
    rows: list[dict] = []

    if granularity == "monthly":
        today = date.today()
        y, m = today.year, today.month
        month_keys = []
        for _ in range(periods):
            month_keys.append(f"{y}-{m:02d}")
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        month_keys.reverse()

        for rep in reps:
            for p in month_keys:
                start, end = _period_bounds(p)
                deals = (await db.execute(select(PipelineDeal).where(
                    PipelineDeal.user_id == rep.id, PipelineDeal.archived == False,
                    PipelineDeal.is_seed == False, PipelineDeal.stage == "closed_won",
                    won_date_col().isnot(None),
                    won_date_col() >= start, won_date_col() <= end,
                ))).scalars().all()
                targets = (await db.execute(select(RevenueTarget).where(
                    RevenueTarget.user_id == rep.id, RevenueTarget.period == p,
                    RevenueTarget.target_type == "revenue",
                ))).scalars().all()
                target_amount = sum(float(t.target_amount) for t in targets)
                amts = [_deal_revenue(d) for d in deals]
                arr = sum(a["arr"] for a in amts)
                one_time = sum(a["one_time"] for a in amts)
                total = sum(a["total"] for a in amts)
                rows.append({
                    "rep_name": rep.name, "region": rep.region, "business": rep.business,
                    "period": p, "arr_achieved": round(arr, 2), "one_time_achieved": round(one_time, 2),
                    "total_achieved": round(total, 2), "revenue_target": round(target_amount, 2),
                    "achievement_pct": round(total / target_amount * 100, 1) if target_amount else None,
                    "deals_won": len(deals),
                })
    else:
        today = date.today()
        month_start = today.replace(day=1)
        for rep in reps:
            deals = (await db.execute(select(PipelineDeal).where(
                PipelineDeal.user_id == rep.id, PipelineDeal.archived == False,
                PipelineDeal.is_seed == False, PipelineDeal.stage == "closed_won",
                won_date_col().isnot(None),
                won_date_col() >= month_start, won_date_col() <= today,
            ))).scalars().all()
            by_week: dict = {}
            for d in deals:
                monday = won_date_of(d) - timedelta(days=won_date_of(d).weekday())
                by_week.setdefault(monday.isoformat(), []).append(d)
            for wk in sorted(by_week.keys()):
                amts = [_deal_revenue(d) for d in by_week[wk]]
                rows.append({
                    "rep_name": rep.name, "region": rep.region, "business": rep.business,
                    "week_of": wk,
                    "arr_booked": round(sum(a["arr"] for a in amts), 2),
                    "one_time_booked": round(sum(a["one_time"] for a in amts), 2),
                    "total_booked": round(sum(a["total"] for a in amts), 2),
                    "deals_won": len(by_week[wk]),
                })

    return _csv_response(rows, f"revenue_vs_target_{granularity}.csv")


@router.get("/rigor-trend.csv", dependencies=[Depends(export_guard("Rigor trend CSV"))])
async def export_rigor_trend(
    granularity: str = "weekly", periods: int = 8,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_any_manager),
):
    """Team-wide CSV over the same per-rep bucketing + aggregate_rigor_breakdown()
    that GET /analytics/rigor-trend/{user_id} (v1.4.3) already does for one
    rep at a time — this is that same, already-tested function, looped
    across every visible rep so a manager can scan the whole team in one
    file instead of opening each rep individually. No new rigor logic."""
    deny_governance(user)
    if granularity not in ("weekly", "monthly"):
        raise HTTPException(400, "granularity must be 'weekly' or 'monthly'")
    reps = await _visible_reps(db, user)
    rows: list[dict] = []

    def bucket_key(d):
        if granularity == "weekly":
            monday = d.date - timedelta(days=d.date.weekday())
            return monday.isoformat()
        return f"{d.date.year}-{d.date.month:02d}"

    for rep in reps:
        dsrs = (await db.execute(
            select(DSRDaily).where(DSRDaily.user_id == rep.id, DSRDaily.is_seed == False)
            .order_by(DSRDaily.date.asc())
        )).scalars().all()
        buckets: dict = {}
        for d in dsrs:
            buckets.setdefault(bucket_key(d), []).append(d)
        for key in sorted(buckets.keys())[-periods:]:
            agg = aggregate_rigor_breakdown(buckets[key])
            rows.append({
                "rep_name": rep.name, "region": rep.region, "business": rep.business,
                "period": key, "avg_rigor": agg["avg_rigor"], "days_counted": agg["days_counted"],
                "weakest_component": agg["weakest"]["label"] if agg["weakest"] else None,
                "weakest_component_pct": agg["weakest"]["earned_pct"] if agg["weakest"] else None,
            })

    return _csv_response(rows, f"rigor_trend_{granularity}.csv")


@router.get("/win-loss.csv", dependencies=[Depends(export_guard("Win-loss CSV"))])
async def export_win_loss(
    include_seed: bool = False,
    db: AsyncSession = Depends(get_db), user: User = Depends(require_any_manager),
):
    """Deal-level CSV behind the same computation as Opportunities' Team
    Win-Loss widget / GET /pipeline/loss-analysis — one row per closed deal
    (won/lost/on_hold/dropped) with outcome detail, where that widget only
    shows aggregate counts. No new win-loss logic, just a flatter view of it."""
    deny_governance(user)
    visible = await resolve_visible_user_ids(db, user)
    show_seed = include_seed and role_level(user.role) >= 40

    q = select(PipelineDeal).where(
        PipelineDeal.archived == False,
        PipelineDeal.stage.in_(["closed_won", "closed_lost", "on_hold", "dropped"]),
    )
    if not show_seed:
        q = q.where(PipelineDeal.is_seed == False)
    if visible is not None:
        q = q.where(PipelineDeal.user_id.in_(visible))
    deals = (await db.execute(q)).scalars().all()

    owner_ids = {d.user_id for d in deals}
    names: dict = {}
    if owner_ids:
        rows_u = (await db.execute(select(User.id, User.name).where(User.id.in_(owner_ids)))).all()
        names = {uid: name for uid, name in rows_u}

    rows = [{
        "company": d.company, "rep_name": names.get(d.user_id, ""), "outcome": d.stage,
        "value": round(_deal_revenue(d)["total"], 2),
        "outcome_category": d.outcome_category or "", "outcome_detail": d.outcome_detail or "",
        "outcome_competitor": d.outcome_competitor or "",
        "closed_date": str((won_date_of(d) if d.stage == "closed_won" else d.closure_eta) or ""),
    } for d in deals]

    return _csv_response(rows, "win_loss_analysis.csv")
