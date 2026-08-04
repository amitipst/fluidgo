"""DSR/DMR/DOR submission-compliance aggregation — closes finding #4 from
the fluidGo data-quality review (2026-07-21/22): there was no submission-
rate/BU visibility anywhere in the app, so a rep or BU simply not filing
DSR was invisible rather than flagged. Even Amit's own "Mine" tab showed
zero July DSRs at the time of that review with nothing calling it out.

Deliberately contains NO financial figures anywhere in its output (no
proposal_value, deal value, incentive amount, or score) — every field here
is a submission-status count or percentage. That's what lets this same
aggregation be reused, unmodified, by BOTH:
  - GET /api/compliance/summary (manager+, their own scope) — the
    dashboard finding #4 asked for.
  - GET /api/governance/compliance (the governance role, org-wide scope) —
    which needs org-wide visibility into WHO is filing on time, but must
    never see money (can_see_financials() in app/models/__init__.py).

"DMR" is not a separate table — see ActivityLogs.tsx's "Pre-Sales DMR"
label. It's the same dsr_daily row a pre_sales/inside_sales user files;
_label_for() below maps role → the label the rest of the app already uses
so this dashboard speaks the same vocabulary reps and managers see
elsewhere (DSR / DMR / DOR), not new terminology.
"""
from datetime import date, datetime, timezone, timedelta
from calendar import monthrange
from typing import Optional, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, DSRDaily, DORDaily

DSR_ROLES = {"rep", "inside_sales", "pre_sales", "manager"}
DOR_ROLES = {"service_delivery_manager"}
PRESALES_ROLES = {"inside_sales", "pre_sales"}

# A rep below this submission-rate is surfaced as "at risk" even if no
# consecutive-miss streak is in progress — catches sporadic (not just
# recent) non-compliance across the whole period.
AT_RISK_THRESHOLD_PCT = 70.0
# Missing this many consecutive expected business days flags a rep as
# at-risk regardless of their overall percentage — this is what makes "gone
# quiet for a week" visible even early in a month, when the percentage
# alone hasn't dropped far yet.
CONSECUTIVE_MISS_ESCALATION = 3


def _label_for(role: str) -> str:
    if role in DOR_ROLES:
        return "DOR"
    if role in PRESALES_ROLES:
        return "DMR"
    return "DSR"


def _business_days(start: date, end: date) -> list:
    """Mon-Fri only. A DSR/DOR entry with status leave/holiday/wfh still
    counts as "submitted" for compliance purposes (the rep logged their
    day) — this function only sets the denominator of expected filing
    days, it doesn't look at DSR status at all."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _submitted_at_date(dt: datetime) -> date:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).date()
    return dt.date()


async def compute_compliance(
    db: AsyncSession,
    visible_ids: Optional[list],
    period: str,
    report_type: Literal["dsr", "dor", "all"] = "all",
) -> dict:
    yr, mo = int(period[:4]), int(period[5:7])
    start = date(yr, mo, 1)
    end = date(yr, mo, monthrange(yr, mo)[1])
    today = datetime.now(timezone.utc).date()
    effective_end = min(end, today)
    expected_days = _business_days(start, effective_end) if effective_end >= start else []
    expected_count = len(expected_days)

    roles = DSR_ROLES | DOR_ROLES
    if report_type == "dsr":
        roles = DSR_ROLES
    elif report_type == "dor":
        roles = DOR_ROLES

    q = select(User).where(User.is_active == True, User.role.in_(roles))
    if visible_ids is not None:
        q = q.where(User.id.in_(visible_ids))
    users = (await db.execute(q)).scalars().all()

    reps = []
    for u in users:
        label = _label_for(u.role)
        if label == "DOR":
            rows = (await db.execute(select(DORDaily).where(
                DORDaily.user_id == u.id,
                DORDaily.report_date >= start, DORDaily.report_date <= end,
            ))).scalars().all()
            submitted_dates = {r.report_date for r in rows}
            # DOR has no backfill-window/late concept like DSR (see dor.py's
            # module docstring — any save resets to "submitted", no self-
            # edit window to be late against), so late_days is always 0.
            late_count = 0
        else:
            rows = (await db.execute(select(DSRDaily).where(
                DSRDaily.user_id == u.id, DSRDaily.is_seed == False,
                DSRDaily.date >= start, DSRDaily.date <= end,
            ))).scalars().all()
            submitted_dates = {r.date for r in rows}
            late_count = sum(
                1 for r in rows
                if r.submitted_at and _submitted_at_date(r.submitted_at) > r.date
            )

        submitted_count = len(submitted_dates)
        missed = [d for d in expected_days if d not in submitted_dates]

        # Consecutive missed business days, trailing backwards from the
        # most recent expected day — distinguishes "missed one day two
        # weeks ago" from "hasn't filed all week", which a flat percentage
        # alone can't tell apart.
        consecutive_missed = 0
        for d in reversed(expected_days):
            if d in submitted_dates:
                break
            consecutive_missed += 1

        compliance_pct = (
            round(submitted_count / expected_count * 100, 1) if expected_count else 100.0
        )
        at_risk = compliance_pct < AT_RISK_THRESHOLD_PCT or consecutive_missed >= CONSECUTIVE_MISS_ESCALATION

        reps.append({
            "user_id": str(u.id), "name": u.name, "email": u.email, "role": u.role,
            "report_type": label, "region": u.region, "business": u.business,
            "expected_days": expected_count, "submitted_days": submitted_count,
            "late_days": late_count,
            "compliance_pct": compliance_pct,
            "consecutive_missed_days": consecutive_missed,
            "last_submitted_date": max(submitted_dates).isoformat() if submitted_dates else None,
            "missed_recent": [d.isoformat() for d in missed[-5:]],
            "at_risk": at_risk,
        })

    reps.sort(key=lambda r: r["compliance_pct"])

    by_region: dict = {}
    for r in reps:
        key = r["region"] or "Unassigned"
        agg = by_region.setdefault(key, {"region": key, "team_size": 0, "_sum": 0.0, "at_risk_count": 0})
        agg["team_size"] += 1
        agg["_sum"] += r["compliance_pct"]
        if r["at_risk"]:
            agg["at_risk_count"] += 1
    by_region_out = []
    for row in by_region.values():
        row["avg_compliance_pct"] = round(row.pop("_sum") / row["team_size"], 1) if row["team_size"] else 0.0
        by_region_out.append(row)
    by_region_out.sort(key=lambda r: r["avg_compliance_pct"])

    return {
        "period": period,
        "report_type": report_type,
        "expected_days": expected_count,
        "reps": reps,
        "summary": {
            "total_reps": len(reps),
            "avg_compliance_pct": round(sum(r["compliance_pct"] for r in reps) / len(reps), 1) if reps else 0.0,
            "at_risk_count": sum(1 for r in reps if r["at_risk"]),
            "by_region": by_region_out,
        },
    }
