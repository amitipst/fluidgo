"""Config-driven weighted scorer. Weights and which metrics compose a role's score
live in scoring_templates/scoring_parameters (DB rows, editable via
/api/scoring/templates) — this module never hardcodes a weight. The metric
*calculators* below are a small fixed registry of pure functions reusing existing
aggregation logic (rigor_service, DSRDaily/Meeting/PipelineDeal queries) — adding a
full formula-expression language is out of scope for Phase 1 (noted in the plan)."""
from calendar import monthrange
from datetime import date, datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import DSRDaily, Meeting, PipelineDeal, SelfScore, User
from app.repositories import scoring_repo
from app.services.rigor_service import calculate_rigor_score, bant_score


def _period_bounds(period: str) -> tuple[date, date]:
    """'2026-07' (month) | '2026-Q3' (quarter) | '2026' (year) -> (start, end) dates."""
    if "-Q" in period:
        year_s, q_s = period.split("-Q")
        year, q = int(year_s), int(q_s)
        start_month = (q - 1) * 3 + 1
        start = date(year, start_month, 1)
        end_month, end_year = start_month + 2, year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        return start, date(end_year, end_month, monthrange(end_year, end_month)[1])
    if "-" in period:
        year_s, month_s = period.split("-")
        year, month = int(year_s), int(month_s)
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])
    year = int(period)
    return date(year, 1, 1), date(year, 12, 31)


async def _metric_revenue_target_achievement_pct(db: AsyncSession, user: User, period: str) -> float:
    target = await scoring_repo.get_target(db, user.id, period)
    if not target or not target.target_amount:
        return 0.0
    start, end = _period_bounds(period)
    result = await db.execute(
        select(PipelineDeal).where(PipelineDeal.user_id == user.id, PipelineDeal.stage == "closed_won",
                                    PipelineDeal.closure_eta >= start, PipelineDeal.closure_eta <= end)
    )
    won = sum(float(d.deal_value or 0) for d in result.scalars().all())
    return min(100.0, (won / float(target.target_amount)) * 100)


async def _metric_activity_rigor_avg(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == user.id, DSRDaily.date >= start, DSRDaily.date <= end)
    )
    dsrs = [d for d in result.scalars().all() if d.status == "working"]
    return (sum(calculate_rigor_score(d) for d in dsrs) / len(dsrs)) if dsrs else 0.0


async def _metric_activity_dsr_compliance_pct(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == user.id, DSRDaily.date >= start, DSRDaily.date <= end)
    )
    submitted = len(result.scalars().all())
    calendar_days = (end - start).days + 1
    return min(100.0, (submitted / calendar_days) * 100) if calendar_days > 0 else 0.0


async def _metric_pipeline_bant_avg(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(Meeting).where(Meeting.user_id == user.id, Meeting.date >= start, Meeting.date <= end)
    )
    meetings = result.scalars().all()
    return (sum(bant_score(m)["closure_pct"] for m in meetings) / len(meetings)) if meetings else 0.0


async def _metric_quality_self_score_avg(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(SelfScore).join(DSRDaily, SelfScore.dsr_id == DSRDaily.id)
        .where(DSRDaily.user_id == user.id, DSRDaily.date >= start, DSRDaily.date <= end)
    )
    per_dsr_avgs = []
    for s in result.scalars().all():
        fields = [s.market_coverage, s.lead_generation, s.followup_discipline, s.quality_of_conv, s.commitment_to_close]
        present = [f for f in fields if f is not None]
        if present:
            per_dsr_avgs.append(sum(present) / len(present))
    return (sum(per_dsr_avgs) / len(per_dsr_avgs)) * 20 if per_dsr_avgs else 0.0  # 0-5 scale -> 0-100


async def _metric_presales_support_activity_pct(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    active = await db.execute(
        select(PipelineDeal).where(PipelineDeal.presales_owner_id == user.id,
                                    PipelineDeal.last_activity_at.isnot(None),
                                    PipelineDeal.last_activity_at >= start, PipelineDeal.last_activity_at <= end)
    )
    total = await db.execute(select(PipelineDeal).where(PipelineDeal.presales_owner_id == user.id))
    total_n = len(total.scalars().all())
    return min(100.0, (len(active.scalars().all()) / total_n) * 100) if total_n else 0.0


async def _metric_presales_win_rate_pct(db: AsyncSession, user: User, period: str) -> float:
    result = await db.execute(
        select(PipelineDeal).where(PipelineDeal.presales_owner_id == user.id,
                                    PipelineDeal.stage.in_(["closed_won", "closed_lost"]))
    )
    deals = result.scalars().all()
    if not deals:
        return 0.0
    return (sum(1 for d in deals if d.stage == "closed_won") / len(deals)) * 100


async def _get_manual_metric_value(db: AsyncSession, user: User, metric_key: str, period: str) -> float:
    """Value for a 'manual.*' metric_source — entered via the Manual KPI Entry
    screen instead of computed from DSR/pipeline data. Missing entry = 0, same
    as any other metric with no activity that period."""
    from app.models import ManualMetricEntry
    result = await db.execute(
        select(ManualMetricEntry).where(
            ManualMetricEntry.user_id == user.id,
            ManualMetricEntry.metric_key == metric_key,
            ManualMetricEntry.period == period,
        )
    )
    entry = result.scalar_one_or_none()
    return float(entry.value) if entry else 0.0


def resolve_tier_multiplier(value: float, tiers: list) -> float:
    """Looks `value` (0-100 achievement, or whatever scale the tiers use) up
    against a parameter's tier bands to find its multiplier. Each tier is
    {"label": str, "min": float|None, "max": float|None, "multiplier": float|None,
    "formula": str|None}. Bounds are half-open: min <= value < max (top tier's
    max is None = open-ended, bottom tier's min is None = -infinity).
    "formula": "square" computes multiplier = (value/100)**2 instead of using
    a flat number — e.g. a KRA scored as "square of achievement" above a
    qualifying threshold, rewarding values close to 100% disproportionately."""
    for tier in (tiers or []):
        lo, hi = tier.get("min"), tier.get("max")
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        if tier.get("formula") == "square":
            return (value / 100.0) ** 2
        return float(tier.get("multiplier") or 0.0)
    return 0.0  # no tier matched — misconfigured template, fail safe to 0


METRIC_REGISTRY = {
    "revenue.target_achievement_pct": _metric_revenue_target_achievement_pct,
    "activity.rigor_avg": _metric_activity_rigor_avg,
    "activity.dsr_compliance_pct": _metric_activity_dsr_compliance_pct,
    "pipeline.bant_avg": _metric_pipeline_bant_avg,
    "quality.self_score_avg": _metric_quality_self_score_avg,
    "presales.support_activity_pct": _metric_presales_support_activity_pct,
    "presales.win_rate_pct": _metric_presales_win_rate_pct,
}

# rep/inside_sales have no org_role_key by default (v2 role mapping is opt-in via
# /api/users or /api/roles) — this fallback lets scoring work immediately without
# requiring every existing seeded user to be re-mapped first.
LEGACY_ROLE_FALLBACK = {
    "rep": "sales", "inside_sales": "presales",
    "service_delivery_manager": "service_delivery",
}


async def compute_score(db: AsyncSession, user: User, period: str) -> dict:
    role_key = user.org_role_key or LEGACY_ROLE_FALLBACK.get(user.role)
    if not role_key:
        return {"score": None, "breakdown": [], "template_id": None,
                "message": f"No scoring template mapped to role '{user.role}'"}

    template = await scoring_repo.get_active_template(db, role_key)
    if not template:
        return {"score": None, "breakdown": [], "template_id": None,
                "message": f"No active scoring template for role '{role_key}'"}

    cached = await scoring_repo.get_cached_result(db, user.id, template.id, period)
    if cached:
        return {"score": float(cached.score), "breakdown": cached.breakdown,
                "template_id": str(template.id), "cached": True}

    parameters = [p for p in await scoring_repo.get_parameters(db, template.id) if p.is_active]
    breakdown, total = [], 0.0
    for p in parameters:
        if p.metric_source.startswith("manual."):
            value = await _get_manual_metric_value(db, user, p.metric_source, period)
        else:
            calc = METRIC_REGISTRY.get(p.metric_source)
            value = await calc(db, user, period) if calc else 0.0
        weight = float(p.weight_pct)

        row = {"name": p.name, "weight_pct": weight, "value": round(value, 1)}
        if p.calc_type == "tiered":
            multiplier = resolve_tier_multiplier(value, p.tiers)
            contribution = weight * multiplier
            row["multiplier"] = round(multiplier, 3)
        else:
            contribution = value * (weight / 100.0)
        row["contribution"] = round(contribution, 2)
        total += contribution
        breakdown.append(row)

    score = round(total, 1)
    await scoring_repo.save_result(db, user.id, template.id, period, score, breakdown)
    return {"score": score, "breakdown": breakdown, "template_id": str(template.id), "cached": False}
