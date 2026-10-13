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
                                    PipelineDeal.closure_eta >= start, PipelineDeal.closure_eta <= end,
                                    PipelineDeal.archived == False, PipelineDeal.is_seed == False)
    )
    won = sum(float(d.deal_value or 0) for d in result.scalars().all())
    return min(100.0, (won / float(target.target_amount)) * 100)


async def _metric_activity_rigor_avg(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == user.id, DSRDaily.date >= start, DSRDaily.date <= end,
                                DSRDaily.is_seed == False)
    )
    dsrs = [d for d in result.scalars().all() if d.status == "working"]
    return (sum(calculate_rigor_score(d) for d in dsrs) / len(dsrs)) if dsrs else 0.0


async def _metric_activity_dsr_compliance_pct(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == user.id, DSRDaily.date >= start, DSRDaily.date <= end,
                                DSRDaily.is_seed == False)
    )
    submitted = len(result.scalars().all())
    calendar_days = (end - start).days + 1
    return min(100.0, (submitted / calendar_days) * 100) if calendar_days > 0 else 0.0


async def _metric_pipeline_bant_avg(db: AsyncSession, user: User, period: str) -> float:
    start, end = _period_bounds(period)
    result = await db.execute(
        select(Meeting).where(Meeting.user_id == user.id, Meeting.date >= start, Meeting.date <= end,
                               Meeting.is_seed == False)
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
                                    PipelineDeal.last_activity_at >= start, PipelineDeal.last_activity_at <= end,
                                    PipelineDeal.archived == False, PipelineDeal.is_seed == False)
    )
    total = await db.execute(select(PipelineDeal).where(
        PipelineDeal.presales_owner_id == user.id,
        PipelineDeal.archived == False, PipelineDeal.is_seed == False))
    total_n = len(total.scalars().all())
    return min(100.0, (len(active.scalars().all()) / total_n) * 100) if total_n else 0.0


async def _metric_presales_win_rate_pct(db: AsyncSession, user: User, period: str) -> float:
    result = await db.execute(
        select(PipelineDeal).where(PipelineDeal.presales_owner_id == user.id,
                                    PipelineDeal.stage.in_(["closed_won", "closed_lost"]),
                                    PipelineDeal.archived == False, PipelineDeal.is_seed == False)
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


def find_tier(value: float, tiers: list) -> dict | None:
    """The tier band `value` falls into, or None if none matched (misconfigured
    template). Bounds are half-open: min <= value < max (top tier's max is None
    = open-ended, bottom tier's min is None = -infinity)."""
    for tier in (tiers or []):
        lo, hi = tier.get("min"), tier.get("max")
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        return tier
    return None


def resolve_tier_multiplier(value: float, tiers: list) -> float:
    """Looks `value` (0-100 achievement, or whatever scale the tiers use) up
    against a parameter's tier bands to find its multiplier. Each tier is
    {"label": str, "min": float|None, "max": float|None, "multiplier": float|None,
    "formula": str|None, "cap": float|None}.
    "formula": "square" computes multiplier = (value/100)**2 instead of using a
    flat number — e.g. a KRA scored as "square of achievement" above a
    qualifying threshold, rewarding values close to 100% disproportionately.
    "formula": "linear" computes multiplier = value/100 — straight proportionate
    scoring within a band (e.g. "80% to 100% = proportionate").
    "cap": if present on a "square"/"linear" tier, the computed multiplier is
    clamped to this ceiling — e.g. an open-ended top tier ("110%+, square of
    achievement, capped at 169%") uses {"min": 110, "formula": "square",
    "cap": 1.69} so unlimited overachievement still tops out at 1.69x rather
    than climbing forever or (worse) falling through to no matching tier."""
    tier = find_tier(value, tiers)
    if tier is None:
        return 0.0  # no tier matched — misconfigured template, fail safe to 0
    formula = tier.get("formula")
    if formula == "square":
        result = (value / 100.0) ** 2
    elif formula == "linear":
        result = value / 100.0
    else:
        return float(tier.get("multiplier") or 0.0)
    cap = tier.get("cap")
    return min(result, cap) if cap is not None else result


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

        row = {"name": p.name, "weight_pct": weight, "value": round(value, 1),
               "is_bonus": bool(p.is_bonus)}
        if p.calc_type == "tiered":
            tier = find_tier(value, p.tiers) if p.is_bonus else None
            if tier is not None and tier.get("formula") == "per_unit":
                # Bonus-only shape: raw value (e.g. a count) x a flat point
                # value per unit, uncapped — "0.5 pts per 5% over target"
                # rather than a multiplier applied to a weight.
                contribution = value * float(tier.get("unit_value") or 0)
                row["unit_value"] = tier.get("unit_value")
            else:
                multiplier = resolve_tier_multiplier(value, p.tiers)
                contribution = weight * multiplier
                row["multiplier"] = round(multiplier, 3)
        else:
            contribution = value * (weight / 100.0)
        row["contribution"] = round(contribution, 2)
        # Bonus lines add straight onto the total — they sit outside the
        # 100%-weighted base split (see 0031_kra_bonus_lines.py) and are
        # excluded from the weight-sum-to-100 validation on save.
        total += contribution
        breakdown.append(row)

    score = round(total, 1)
    await scoring_repo.save_result(db, user.id, template.id, period, score, breakdown)
    return {"score": score, "breakdown": breakdown, "template_id": str(template.id), "cached": False}
