from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal
from app.database import get_db
from app.models import PipelineDeal, User
from app.services.deps import get_current_user
from app.services.audit_service import audit

router = APIRouter()

class DealIn(BaseModel):
    company: str
    stage: Literal["cold", "warm", "hot", "closed_won", "closed_lost"] = "cold"
    todays_update: Optional[str] = None
    roadblock: bool = False
    next_step: Optional[str] = None
    closure_eta: Optional[date] = None
    deal_value: Optional[float] = None
    # ── v2 Opportunity fields — all optional, existing callers unaffected ──
    bu: Optional[str] = None
    presales_owner_id: Optional[str] = None
    primary_contact: Optional[str] = None
    oem: Optional[str] = None
    solution_area: Optional[Literal["Managed Services", "Cloud", "Licensing", "Security", "Professional Services"]] = None
    practice: Optional[str] = None
    recurring_revenue: Optional[float] = None
    one_time_revenue: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    competition: Optional[str] = None
    risk_level: Optional[Literal["low", "medium", "high", "critical"]] = None
    decision_maker: Optional[str] = None
    budget_status: Optional[Literal["confirmed", "unconfirmed", "unknown"]] = None
    timeline_status: Optional[Literal["on_track", "delayed", "unknown"]] = None
    proposal_version: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None

@router.post("")
async def create_deal(body: DealIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    deal = PipelineDeal(user_id=user.id, **body.model_dump())
    db.add(deal)
    await db.commit()
    return {"id": str(deal.id), **body.model_dump()}

@router.get("")
async def list_deals(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(PipelineDeal).where(PipelineDeal.user_id == user.id).order_by(PipelineDeal.updated_at.desc())
    )
    return [{c.name: getattr(d, c.name) for c in d.__table__.columns} for d in result.scalars().all()]

@router.patch("/{deal_id}")
async def update_deal(deal_id: str, body: DealIn, request: Request,
                      background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    result = await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")

    updates = body.model_dump(exclude_none=True)
    # Capture value/stage changes specifically — these feed revenue forecasting,
    # so a change to them is worth an explicit audit entry.
    old_value = float(deal.deal_value) if deal.deal_value is not None else None
    old_stage = deal.stage

    for k, v in updates.items():
        setattr(deal, k, v)
    # Any edit counts as activity — keeps "stale deal" logic honest.
    deal.last_activity_at = datetime.utcnow()
    await db.commit()

    new_value = float(deal.deal_value) if deal.deal_value is not None else None
    changes = []
    if "deal_value" in updates and old_value != new_value:
        changes.append(f"value {old_value or 0:,.0f} → {new_value or 0:,.0f}")
    if "stage" in updates and old_stage != deal.stage:
        changes.append(f"stage {old_stage} → {deal.stage}")
    if changes:
        background_tasks.add_task(
            audit, db, user, "UPDATE", "pipeline", deal_id,
            f"{deal.company}: {', '.join(changes)}", request=request,
        )
    return {"id": deal_id, "updated": True}


# ── Structured close (win / loss / hold / drop) with reason taxonomy ──────────
# Fixed taxonomy so losses are analysable in aggregate. Grouped by outcome.
OUTCOME_TAXONOMY = {
    "closed_lost": ["price", "competitor", "no_decision", "lost_champion",
                    "technical_fit", "in_house", "budget_cut", "other"],
    "on_hold":     ["budget_frozen", "deprioritized", "awaiting_approval",
                    "contract_cycle", "other"],
    "dropped":     ["no_genuine_need", "unresponsive", "not_icp",
                    "disqualified", "duplicate", "other"],
    "closed_won":  ["value_fit", "relationship", "technical_win", "price_win",
                    "incumbent_advantage", "other"],
}
REENGAGE_DEFAULT_MONTHS_BEFORE = 4  # resurface 4mo before the incumbent contract expires

class CloseDealIn(BaseModel):
    outcome: Literal["closed_won", "closed_lost", "on_hold", "dropped"]
    category: str                                  # must be in OUTCOME_TAXONOMY[outcome]
    detail: Optional[str] = None                   # rep's free-text explanation
    competitor: Optional[str] = None               # who won (for competitor losses)
    # Contract details — for won deals, OR deals lost to a competitor on a fixed term.
    contract_months: Optional[int] = None          # 12 / 24 / 36 ...
    reengage_at: Optional[date] = None             # rep override for the win-back date

@router.post("/{deal_id}/close")
async def close_deal(deal_id: str, body: CloseDealIn, request: Request,
                     background_tasks: BackgroundTasks,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """Close a deal with a STRUCTURED reason. For lost/hold/dropped this drives
    win-loss learning + an AI post-mortem. For won/competitor-lost fixed-term
    contracts, it schedules a win-back alert before the contract expires."""
    def add_months(d: date, months: int) -> date:
        # No external dep: roll year/month, clamp day to end-of-month if needed.
        m = d.month - 1 + months
        y = d.year + m // 12
        m = m % 12 + 1
        # clamp day (e.g. Jan 31 + 1mo → Feb 28)
        import calendar
        day = min(d.day, calendar.monthrange(y, m)[1])
        return date(y, m, day)

    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")

    valid = OUTCOME_TAXONOMY.get(body.outcome, [])
    if body.category not in valid:
        raise HTTPException(400, f"category for {body.outcome} must be one of: {', '.join(valid)}")

    deal.stage               = body.outcome
    deal.outcome_category    = body.category
    deal.outcome_detail      = body.detail
    deal.outcome_competitor  = body.competitor
    deal.outcome_recorded_at = datetime.utcnow()

    # Contract win-back scheduling (won deals, or lost-to-competitor on a term)
    if body.contract_months and body.contract_months > 0:
        deal.contract_months   = body.contract_months
        deal.contract_end_date = add_months(date.today(), body.contract_months)
        deal.reengage_at       = body.reengage_at or add_months(
            deal.contract_end_date, -REENGAGE_DEFAULT_MONTHS_BEFORE)
        deal.reengage_done     = False

    await db.commit()

    # AI post-mortem for anything that didn't close won (the learning cases)
    if body.outcome in ("closed_lost", "on_hold", "dropped"):
        background_tasks.add_task(generate_deal_postmortem, deal_id)

    background_tasks.add_task(
        audit, db, user, "CLOSE_DEAL", "pipeline", deal_id,
        f"{deal.company}: {body.outcome} ({body.category})"
        + (f" vs {body.competitor}" if body.competitor else ""),
        request=request,
    )
    return {"id": deal_id, "outcome": body.outcome,
            "reengage_at": deal.reengage_at.isoformat() if deal.reengage_at else None}


async def generate_deal_postmortem(deal_id: str):
    """Background AI post-mortem: given the structured loss reason + deal context,
    produce 'what went wrong + how to improve next time'. Written to the deal."""
    from app.database import AsyncSessionLocal
    from app.services.ai_service import analyse
    async with AsyncSessionLocal() as db:
        deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == uuid_or_none(deal_id)))).scalar_one_or_none()
        if not deal:
            return
        context = f"""A B2B IT sales deal did not close successfully. Analyse what went wrong and give specific, actionable coaching for next time.

Deal: {deal.company}
Outcome: {deal.stage} (reason category: {deal.outcome_category})
{'Lost to competitor: ' + deal.outcome_competitor if deal.outcome_competitor else ''}
Deal value: {deal.deal_value or 'unknown'}
Solution area: {deal.solution_area or 'unknown'}
Rep's explanation: {deal.outcome_detail or 'none provided'}
Deal health at close: {deal.ai_deal_health or 'unknown'}/100
Decision maker identified: {deal.decision_maker or 'no'}
Budget status: {deal.budget_status or 'unknown'}

Give: 1) Root cause (what really went wrong), 2) The earliest warning sign that was missed, 3) Two specific things to do differently on similar deals. Be direct and practical."""
        try:
            analysis = await analyse(context, prompt_type="deal_postmortem")
        except Exception as e:
            analysis = None
        if analysis and not analysis.startswith("⚠️"):
            deal.outcome_ai_analysis = analysis
            await db.commit()


def uuid_or_none(v):
    import uuid as _uuid
    try:
        return _uuid.UUID(str(v))
    except Exception:
        return None


@router.get("/{deal_id}/postmortem")
async def get_postmortem(deal_id: str, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """Fetch the AI post-mortem for a closed deal (rep + their manager)."""
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    return {
        "outcome": deal.stage,
        "category": deal.outcome_category,
        "detail": deal.outcome_detail,
        "competitor": deal.outcome_competitor,
        "ai_analysis": deal.outcome_ai_analysis,
        "status": "ready" if deal.outcome_ai_analysis else "pending",
    }


@router.get("/loss-analysis")
async def loss_analysis(db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Aggregate win-loss summary + AI pattern analysis across the caller's
    visible deals. Rep sees own; manager sees team."""
    from app.models import role_level
    from app.services.permission_service import resolve_visible_user_ids
    from sqlalchemy import func

    if role_level(user.role) >= 20:
        visible = await resolve_visible_user_ids(db, user)
    else:
        visible = [user.id]

    q = select(PipelineDeal)
    if visible is not None:
        q = q.where(PipelineDeal.user_id.in_(visible))
    deals = (await db.execute(q)).scalars().all()

    lost    = [d for d in deals if d.stage == "closed_lost"]
    held    = [d for d in deals if d.stage == "on_hold"]
    dropped = [d for d in deals if d.stage == "dropped"]
    won     = [d for d in deals if d.stage == "closed_won"]

    def by_category(rows):
        counts: dict = {}
        for d in rows:
            c = d.outcome_category or "unspecified"
            counts[c] = counts.get(c, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    lost_value = sum(float(d.deal_value or 0) for d in lost)
    won_value  = sum(float(d.deal_value or 0) for d in won)
    total_closed = len(won) + len(lost)
    win_rate = round(100 * len(won) / total_closed) if total_closed else 0

    return {
        "is_team": role_level(user.role) >= 20,
        "counts": {"won": len(won), "lost": len(lost), "on_hold": len(held), "dropped": len(dropped)},
        "lost_value": lost_value,
        "won_value": won_value,
        "win_rate": win_rate,
        "lost_by_category": by_category(lost),
        "hold_by_category": by_category(held),
        "dropped_by_category": by_category(dropped),
        "competitors": by_category([d for d in lost if d.outcome_competitor]) if False else
                       dict(sorted({
                           (d.outcome_competitor or "unknown"): 1 for d in lost if d.outcome_competitor
                       }.items())),
    }


@router.get("/win-back-alerts")
async def win_back_alerts(db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """Deals (won or lost-to-competitor on a fixed term) whose re-engage date
    has arrived — i.e. the incumbent contract is nearing expiry. This turns a
    past loss into a future opportunity."""
    from app.models import role_level
    from app.services.permission_service import resolve_visible_user_ids

    if role_level(user.role) >= 20:
        visible = await resolve_visible_user_ids(db, user)
    else:
        visible = [user.id]

    q = select(PipelineDeal).where(
        PipelineDeal.reengage_at.isnot(None),
        PipelineDeal.reengage_done == False,
        PipelineDeal.reengage_at <= date.today(),
    )
    if visible is not None:
        q = q.where(PipelineDeal.user_id.in_(visible))
    deals = (await db.execute(q.order_by(PipelineDeal.reengage_at))).scalars().all()

    return [{
        "id": str(d.id), "company": d.company,
        "outcome": d.stage, "competitor": d.outcome_competitor,
        "contract_end_date": d.contract_end_date.isoformat() if d.contract_end_date else None,
        "reengage_at": d.reengage_at.isoformat() if d.reengage_at else None,
        "deal_value": float(d.deal_value or 0),
        "solution_area": d.solution_area,
    } for d in deals]


@router.post("/{deal_id}/win-back-done")
async def win_back_done(deal_id: str, request: Request, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Rep dismisses / actions a win-back alert (so it stops resurfacing)."""
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    deal.reengage_done = True
    await db.commit()
    return {"id": deal_id, "reengage_done": True}
