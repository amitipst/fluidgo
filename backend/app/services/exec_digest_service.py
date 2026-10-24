"""Executive Intelligence Digest — added 2026-10-24.

Build-vs-buy decision already made in `fluidgo-services-intelligence-platform
-assessment.md`'s R2: "Existing Analytics/Dashboards + AI-coaching-insight
pattern + existing SMTP -> a scheduled digest job... genuinely one of the
cheapest, highest-visibility wins available." Scored directly against Amit's
instruction to benchmark every feature against "sales cadence, sales
intelligence and business revenue, with better insights and better
outcomes" — this is the single release that touches all three at once: a
recurring (cadence) surfaced-insight (intelligence) view of revenue
progress, pipeline risk and team execution health (outcomes), without
inventing anything new under the hood.

Deliberately reuses ONLY existing, already-tested computations — zero new
scoring/aggregation logic:
  - pipeline_sheet_service.amounts() for every revenue figure (the one
    ARR+One-time+deal_value-fallback rule, same as every other place in the
    app that sums a deal's value, per the v1.4.3/v1.4.4 lesson about that
    exact bug class).
  - rigor_service.aggregate_rigor_breakdown() for team activity rigor.
  - compliance_service.compute_compliance() for DSR/DOR submission health.
  - permission_service.resolve_visible_user_ids() for scope — a business_head
    sees their business, a CEO sees everything, same as every other screen.

Does NOT build the generalized `interactions`/`health_engine` primitive from
the platform assessment's R1 — that's a separate, larger decision still
awaiting Amit's multi-tenancy answer (see that doc's §3.5) and isn't a
prerequisite for this digest, which only reads data that already exists.
No escalation/CAPA section either — Escalation Management doesn't exist yet
(R3, not built); adding a stub here would mean either fabricating data or a
permanently-empty section, so it's left out of v1 rather than faked.
"""
from datetime import date, datetime, timedelta, timezone
from calendar import monthrange

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, PipelineDeal, DSRDaily, RevenueTarget
from app.services.pipeline_sheet_service import amounts as _amounts
from app.services.rigor_service import aggregate_rigor_breakdown
from app.services.compliance_service import compute_compliance
from app.services.permission_service import resolve_visible_user_ids

STALE_DEAL_DAYS = 14  # an open deal with no logged activity in this many days surfaces as at-risk


def _current_period() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _deal_value(d: PipelineDeal) -> float:
    return _amounts(d.recurring_revenue, d.one_time_revenue, d.deal_value)["total"]


def _serialize_deal(d: PipelineDeal) -> dict:
    return {
        "id": str(d.id), "company": d.company, "stage": d.stage,
        "value": round(_deal_value(d), 2),
        "last_activity_at": d.last_activity_at.isoformat() if d.last_activity_at else None,
    }


async def build_digest(db: AsyncSession, user: User, period: str | None = None) -> dict:
    period = period or _current_period()
    yr, mo = int(period[:4]), int(period[5:7])
    start, end = date(yr, mo, 1), date(yr, mo, monthrange(yr, mo)[1])

    visible_ids = await resolve_visible_user_ids(db, user)

    def _scope(q):
        return q.where(PipelineDeal.user_id.in_(visible_ids)) if visible_ids is not None else q

    # ── Revenue vs target, this period, in scope ─────────────────────────
    won_q = _scope(select(PipelineDeal).where(
        PipelineDeal.stage == "closed_won", PipelineDeal.archived == False, PipelineDeal.is_seed == False,
        PipelineDeal.closure_eta >= start, PipelineDeal.closure_eta <= end,
    ))
    won_deals = (await db.execute(won_q)).scalars().all()
    revenue_achieved = sum(_deal_value(d) for d in won_deals)

    targets_q = select(RevenueTarget).where(RevenueTarget.period == period, RevenueTarget.target_type == "revenue")
    if visible_ids is not None:
        targets_q = targets_q.where(RevenueTarget.user_id.in_(visible_ids))
    targets = (await db.execute(targets_q)).scalars().all()
    revenue_target = sum(float(t.target_amount) for t in targets)
    revenue_achievement_pct = round((revenue_achieved / revenue_target) * 100, 1) if revenue_target else None

    # ── Open pipeline + at-risk + recent wins ────────────────────────────
    open_q = _scope(select(PipelineDeal).where(
        PipelineDeal.archived == False, PipelineDeal.is_seed == False,
        ~PipelineDeal.stage.in_(["closed_won", "closed_lost", "dropped"]),
    ))
    open_deals = (await db.execute(open_q)).scalars().all()
    open_pipeline_value = sum(_deal_value(d) for d in open_deals)
    weighted_forecast = sum(_deal_value(d) * ((d.ai_closure_pct or 0) / 100) for d in open_deals)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DEAL_DAYS)
    at_risk_deals = sorted(
        (d for d in open_deals if not d.last_activity_at or d.last_activity_at < stale_cutoff),
        key=_deal_value, reverse=True,
    )[:5]
    recent_wins = sorted(won_deals, key=_deal_value, reverse=True)[:5]

    # ── Team rigor, this period ──────────────────────────────────────────
    dsr_q = select(DSRDaily).where(
        DSRDaily.date >= start, DSRDaily.date <= end,
        DSRDaily.is_seed == False, DSRDaily.status == "working",
    )
    if visible_ids is not None:
        dsr_q = dsr_q.where(DSRDaily.user_id.in_(visible_ids))
    dsrs = (await db.execute(dsr_q)).scalars().all()
    rigor = aggregate_rigor_breakdown(dsrs)

    # ── Compliance (DSR+DOR submission health) ───────────────────────────
    compliance = await compute_compliance(db, visible_ids, period, "all")
    reps = compliance.get("reps", [])
    compliance_avg = round(sum(r["compliance_pct"] for r in reps) / len(reps), 1) if reps else None
    at_risk_reps = sorted((r for r in reps if r["at_risk"]), key=lambda r: r["compliance_pct"])[:5]

    return {
        "period": period, "generated_at": datetime.now(timezone.utc).isoformat(),
        "revenue": {
            "achieved": round(revenue_achieved, 2),
            "target": round(revenue_target, 2) if revenue_target else None,
            "achievement_pct": revenue_achievement_pct,
        },
        "pipeline": {
            "open_count": len(open_deals), "open_value": round(open_pipeline_value, 2),
            "weighted_forecast": round(weighted_forecast, 2),
            "at_risk": [_serialize_deal(d) for d in at_risk_deals],
            "recent_wins": [_serialize_deal(d) for d in recent_wins],
        },
        "rigor": rigor,
        "compliance": {
            "avg_pct": compliance_avg, "at_risk_count": len(at_risk_reps),
            "at_risk_reps": [
                {"name": r["name"], "compliance_pct": r["compliance_pct"],
                 "consecutive_missed_days": r["consecutive_missed_days"]}
                for r in at_risk_reps
            ],
        },
    }


def _inr(n) -> str:
    if n is None:
        return "—"
    return f"₹{n:,.0f}"


def render_html(digest: dict, recipient_name: str) -> str:
    """Plain, email-client-safe HTML (tables, inline styles) — no external CSS/JS,
    matches the constraints of the existing MOM/password-reset email templates."""
    rev, pipe, rigor, comp = digest["revenue"], digest["pipeline"], digest["rigor"], digest["compliance"]

    def _row(label, value):
        return f'<tr><td style="padding:4px 12px 4px 0;color:#64748b;">{label}</td><td style="padding:4px 0;font-weight:600;">{value}</td></tr>'

    def _deal_rows(deals, empty_msg):
        if not deals:
            return f'<tr><td colspan="2" style="padding:6px 0;color:#94a3b8;font-style:italic;">{empty_msg}</td></tr>'
        return "".join(
            f'<tr><td style="padding:3px 12px 3px 0;">{d["company"]}</td>'
            f'<td style="padding:3px 0;text-align:right;">{_inr(d["value"])}</td></tr>'
            for d in deals
        )

    achievement = f'{rev["achievement_pct"]}%' if rev["achievement_pct"] is not None else "no target set"

    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:0 auto;color:#0f172a;">
      <h2 style="color:#0f172a;">📊 fluidGo Executive Digest — {digest['period']}</h2>
      <p style="color:#64748b;">Hi {recipient_name}, here's where things stand as of {digest['generated_at'][:10]}.</p>

      <h3 style="margin-top:24px;">💰 Revenue</h3>
      <table style="width:100%;border-collapse:collapse;">
        {_row('Achieved', _inr(rev['achieved']))}
        {_row('Target', _inr(rev['target']))}
        {_row('Achievement', achievement)}
      </table>

      <h3 style="margin-top:24px;">📈 Pipeline</h3>
      <table style="width:100%;border-collapse:collapse;">
        {_row('Open deals', pipe['open_count'])}
        {_row('Open pipeline value', _inr(pipe['open_value']))}
        {_row('Weighted forecast', _inr(pipe['weighted_forecast']))}
      </table>

      <h4 style="margin-top:16px;color:#b91c1c;">⚠️ At-risk deals (no activity in {STALE_DEAL_DAYS}+ days)</h4>
      <table style="width:100%;border-collapse:collapse;">{_deal_rows(pipe['at_risk'], 'None — pipeline is current.')}</table>

      <h4 style="margin-top:16px;color:#15803d;">🏆 Recent wins this period</h4>
      <table style="width:100%;border-collapse:collapse;">{_deal_rows(pipe['recent_wins'], 'No closed-won deals yet this period.')}</table>

      <h3 style="margin-top:24px;">🎯 Team Rigor</h3>
      <table style="width:100%;border-collapse:collapse;">
        {_row('Average rigor score', f"{rigor['avg_rigor']}/100" if rigor.get('avg_rigor') is not None else '—')}
        {_row('Weakest component', rigor['weakest']['label'] if rigor.get('weakest') else '—')}
      </table>

      <h3 style="margin-top:24px;">✅ Compliance</h3>
      <table style="width:100%;border-collapse:collapse;">
        {_row('Avg DSR/DOR compliance', f"{comp['avg_pct']}%" if comp['avg_pct'] is not None else '—')}
        {_row('Reps at risk', comp['at_risk_count'])}
      </table>

      <p style="margin-top:28px;color:#94a3b8;font-size:12px;">
        Generated automatically by fluidGo — Executive Digest. Reply to this email with
        questions, or open the Executive Digest page in fluidGo for the live view.
      </p>
    </div>
    """
