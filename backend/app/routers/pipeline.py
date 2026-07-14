from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import PipelineDeal, User, role_level, PipelineUpdate
from app.services.deps import get_current_user
from app.services.audit_service import audit

router = APIRouter()

# ── Stall detection thresholds ────────────────────────────────────────────
# Pure SQL/Python, no LLM call — computed on every list_deals() response from
# last_activity_at (already bumped on every PATCH, see update_deal below).
# on_hold/dropped/closed_* are deliberately excluded: on_hold is an
# intentional pause, closed_* are terminal — "stalled" only means something
# for a deal a rep is supposedly still actively working.
STALL_THRESHOLD_DAYS = 7
OPEN_STAGES = {"cold", "warm", "hot", "qualification"}

class DealIn(BaseModel):
    company: str
    # Must cover every stage value any endpoint can actually put a deal into,
    # not just the ones the Pipeline edit form's own dropdown offers - PATCH
    # always sends the full DealIn body, so an unchanged-but-unlisted current
    # value fails validation and blocks saving ANY field on that deal.
    # "qualification" comes from Leads.convert_lead_to_deal (ConvertLeadIn
    # defaults to it); "on_hold"/"dropped" come from close_deal's outcome
    # taxonomy. Missing these was the "can't edit/reverse a converted lead"
    # bug - every PATCH on such a deal 422'd on the stage field alone.
    stage: Literal["cold", "warm", "hot", "qualification", "on_hold", "dropped",
                   "closed_won", "closed_lost"] = "cold"
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
    """Scoped the same way Opportunities already is: reps see their own
    deals, manager/regional_manager/business_head see their whole visible
    hierarchy via resolve_visible_user_ids (business_head = all regions in
    the business). This was hardcoded to user.id only - Pipeline was
    silently showing just the actor's own deals regardless of role, while
    Opportunities (same underlying `pipeline` table) showed the correct
    scoped set. That's why a Business Head's Pipeline view looked like a
    handful of personal deals instead of the whole BU."""
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    q = select(PipelineDeal)
    if visible is not None:
        q = q.where(PipelineDeal.user_id.in_(visible))
    q = q.order_by(PipelineDeal.updated_at.desc())
    result = await db.execute(q)
    now = datetime.utcnow()
    rows = []
    for d in result.scalars().all():
        row = {c.name: getattr(d, c.name) for c in d.__table__.columns}
        last_touch = d.last_activity_at or d.created_at
        days_since = (now - last_touch).days if last_touch else None
        row["days_since_activity"] = days_since
        row["is_stalled"] = bool(
            d.stage in OPEN_STAGES and days_since is not None and days_since >= STALL_THRESHOLD_DAYS
        )
        rows.append(row)
    return rows

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

    # Today's Update / Next Step used to just overwrite in place, losing the
    # trail of what a rep reported over time. Every save that carries a new
    # todays_update now also appends a PipelineUpdate history row (old
    # remarks are never lost), and snapshots the stage at the time — this
    # becomes the ordered sequence the History timeline + future AI trend
    # analysis (stall detection, momentum) reads from.
    if "todays_update" in updates and updates["todays_update"]:
        db.add(PipelineUpdate(
            deal_id=deal.id,
            author_id=user.id,
            update_text=deal.todays_update,
            next_step=deal.next_step,
            stage_at_time=deal.stage,
            created_at=datetime.utcnow(),
        ))

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


@router.get("/{deal_id}/updates")
async def list_deal_updates(deal_id: str, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """Ordered remark history for a deal (newest first) — the History
    timeline on the Pipeline card, and the input sequence for AI trend
    analysis. Same visibility rule as the deal itself: owner, or anyone
    whose scope includes the owner."""
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")

    if deal.user_id != user.id and role_level(user.role) >= 20:
        from app.services.permission_service import resolve_visible_user_ids
        visible = await resolve_visible_user_ids(db, user)
        if visible is not None and deal.user_id not in visible:
            raise HTTPException(403, "You cannot view this deal's history")
    elif deal.user_id != user.id and role_level(user.role) < 20:
        raise HTTPException(403, "You cannot view this deal's history")

    result = await db.execute(
        select(PipelineUpdate, User.name)
        .join(User, User.id == PipelineUpdate.author_id, isouter=True)
        .where(PipelineUpdate.deal_id == deal_id)
        .order_by(PipelineUpdate.created_at.desc())
    )
    return [
        {
            "id": str(entry.id),
            "author_name": author_name,
            "update_text": entry.update_text,
            "next_step": entry.next_step,
            "stage_at_time": entry.stage_at_time,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry, author_name in result.all()
    ]


# ── AI momentum check (on-demand) ──────────────────────────────────────────
# Rep-triggered rather than auto-run on every save, to keep Ollama load
# bounded — same reasoning as generate_deal_postmortem only firing on
# close, not on every edit. Verdict is cached on the deal row so reopening
# the card shows the last check without re-running it.
MOMENTUM_MIN_UPDATES = 2  # need at least 2 remarks to judge a trend


async def _build_momentum_context(db: AsyncSession, deal: PipelineDeal) -> tuple[str, int]:
    """Chronological (oldest-first) remark sequence for the momentum prompt.
    Last 5 updates is enough context for phi3:mini without an oversized prompt."""
    result = await db.execute(
        select(PipelineUpdate)
        .where(PipelineUpdate.deal_id == deal.id)
        .order_by(PipelineUpdate.created_at.desc())
        .limit(5)
    )
    updates = list(reversed(result.scalars().all()))
    lines = [
        f"[{u.created_at.strftime('%d-%b')}, stage={u.stage_at_time or 'unknown'}] "
        f"Update: {u.update_text}" + (f" | Next step: {u.next_step}" if u.next_step else "")
        for u in updates
    ]
    context = f"Deal: {deal.company}\n\n" + "\n".join(lines)
    return context, len(updates)


def _check_deal_access(deal: PipelineDeal, user: User):
    """Same visibility rule as list_deal_updates: owner, or anyone whose
    scope includes the owner. Raises 403 if not permitted."""
    if deal.user_id != user.id and role_level(user.role) < 20:
        raise HTTPException(403, "You cannot access this deal")


@router.post("/{deal_id}/momentum")
async def check_deal_momentum(deal_id: str, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    """Run (or re-run) the AI momentum check over this deal's pipeline_updates
    sequence — has it moved forward, stalled, or gone in circles? Synchronous
    (not a background task): the prompt asks for one short sentence, so it
    finishes well under ai_service.analyse()'s timeout even on this host's
    ~2 tok/s phi3:mini."""
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    _check_deal_access(deal, user)
    if deal.user_id != user.id:
        from app.services.permission_service import resolve_visible_user_ids
        visible = await resolve_visible_user_ids(db, user)
        if visible is not None and deal.user_id not in visible:
            raise HTTPException(403, "You cannot access this deal")

    context, n = await _build_momentum_context(db, deal)
    if n < MOMENTUM_MIN_UPDATES:
        return {"status": "insufficient_history",
                "message": f"Needs at least {MOMENTUM_MIN_UPDATES} logged updates to judge momentum — this deal has {n}."}

    from app.services.ai_service import analyse
    summary = await analyse(context, prompt_type="deal_momentum")
    if summary.startswith("⚠️ AI analysis unavailable"):
        raise HTTPException(503, summary)

    deal.ai_momentum_summary = summary.strip()
    deal.ai_momentum_generated_at = datetime.utcnow()
    await db.commit()
    return {"status": "ready", "summary": deal.ai_momentum_summary,
            "generated_at": deal.ai_momentum_generated_at.isoformat()}


@router.get("/{deal_id}/momentum")
async def get_deal_momentum(deal_id: str, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """Last cached momentum verdict, if one has been generated."""
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    _check_deal_access(deal, user)
    if deal.user_id != user.id:
        from app.services.permission_service import resolve_visible_user_ids
        visible = await resolve_visible_user_ids(db, user)
        if visible is not None and deal.user_id not in visible:
            raise HTTPException(403, "You cannot access this deal")

    return {
        "status": "ready" if deal.ai_momentum_summary else "not_generated",
        "summary": deal.ai_momentum_summary,
        "generated_at": deal.ai_momentum_generated_at.isoformat() if deal.ai_momentum_generated_at else None,
    }


class ReassignIn(BaseModel):
    new_owner_id: str


@router.post("/{deal_id}/reassign")
async def reassign_deal(deal_id: str, body: ReassignIn, request: Request,
                        background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Change a deal's owner — the missing half of CSG Phase 1's flag-opportunity
    flow: a Service Delivery signal defaults to the flagger's manager for
    triage (see dor.py), and THIS is how that manager routes it to the right
    sales rep. Manager-tier+ only, and both the deal's current owner and the
    new owner must be within the actor's visible scope (same rule as any
    other cross-user action in the app)."""
    if role_level(user.role) < 20:
        raise HTTPException(403, "Only managers and above can reassign deals")

    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")

    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and deal.user_id not in visible:
        raise HTTPException(403, "You cannot reassign this deal")

    new_owner_id = uuid.UUID(body.new_owner_id)
    new_owner = (await db.execute(select(User).where(User.id == new_owner_id))).scalar_one_or_none()
    if not new_owner:
        raise HTTPException(404, "New owner not found")
    if visible is not None and new_owner_id not in visible:
        raise HTTPException(403, "You cannot assign this deal to someone outside your scope")

    old_owner_id = deal.user_id
    deal.user_id = new_owner_id
    deal.last_activity_at = datetime.utcnow()
    await db.commit()

    if old_owner_id != new_owner_id:
        background_tasks.add_task(
            audit, db, user, "REASSIGN", "pipeline", deal_id,
            f"{deal.company}: reassigned to {new_owner.name}", request=request,
        )
    return {"id": deal_id, "new_owner_id": str(new_owner_id), "new_owner_name": new_owner.name}


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
