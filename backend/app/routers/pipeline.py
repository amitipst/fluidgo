from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime, timezone
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.services.export_guard import export_guard
from app.models import PipelineDeal, User, role_level, PipelineUpdate, PipelineTargetChange
from app.services.deps import get_current_user, deny_governance
from app.services.audit_service import audit
from app.services import pipeline_sheet_service as sheet
from app.services import deal_rules_service as rules_svc
from app.services.deal_rules_service import RuleViolation
from app.services.crm_link_service import resolve_links, display_name
from app.services import deal_duplicate_service as dup_svc
from app.services import finance_notify_service as fin_svc
from app.services import email_service

router = APIRouter()

# ── Stall detection thresholds ────────────────────────────────────────────
# Pure SQL/Python, no LLM call — computed on every list_deals() response from
# last_activity_at (already bumped on every PATCH, see update_deal below).
# on_hold/dropped/closed_* are deliberately excluded: on_hold is an
# intentional pause, closed_* are terminal — "stalled" only means something
# for a deal a rep is supposedly still actively working.
STALL_THRESHOLD_DAYS = 7
OPEN_STAGES = {"cold", "warm", "hot", "qualification"}

def _aware(dt):
    """Normalize a datetime to UTC-aware so it's safe to compare/subtract.
    Postgres timestamptz columns come back tz-aware via asyncpg, but this
    file (like the rest of the codebase) writes naive datetime.utcnow()
    values - subtracting the two raises TypeError. Same bug class, same
    fix pattern as dsr.py's _aware() (that mismatch caused the earlier
    /dsr/history 500; this one caused list_deals' new stall-detection
    subtraction to 500, which is why Pipeline silently showed 0 deals -
    the frontend's useQuery falls back to an empty array on a failed
    request instead of surfacing the error)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

class DealIn(BaseModel):
    company: Optional[str] = None   # filled from the Contacts master when account_id is sent
    title: Optional[str] = Field(default=None, max_length=150)   # v1.6.0: tells parallel deals apart
    stage_override_reason: Optional[str] = Field(default=None, max_length=200)   # lets a NEW deal start below SP5 (audited)
    # v1.5.0 company-first + SP stage (see deal_rules_service / crm_link_service)
    account_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    sp_stage: Optional[str] = None
    # Won = customer email/LOI/PO/agreement received; revenue = tax invoice raised.
    won_basis: Optional[Literal["email", "loi", "po", "agreement"]] = None
    won_at: Optional[date] = None
    won_ref: Optional[str] = Field(default=None, max_length=120)
    invoiced_at: Optional[date] = None
    invoice_ref: Optional[str] = Field(default=None, max_length=60)
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
    win_probability: Optional[int] = Field(default=None, ge=0, le=100)
    target_note: Optional[str] = Field(default=None, max_length=60)

@router.post("")
async def create_deal(body: DealIn, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rules = await rules_svc.get_rules(db)
    data = body.model_dump()
    try:
        account, contact = await resolve_links(
            db, body.account_id, body.contact_id, rules["require_company_contact"])
        if account is not None:
            data["company"] = account.name
            data["primary_contact"] = display_name(contact) or data.get("primary_contact")
        if not (data.get("company") or "").strip():
            raise RuleViolation("Company is required.")
        rules_svc.validate_revenue_split(body.recurring_revenue, body.one_time_revenue, data["stage"] if body.sp_stage != "won" else "closed_won", rules)
        sp_stage = body.sp_stage or ("won" if body.stage == "closed_won" else rules["deal_start_stage"])
        if sp_stage not in rules["stages"]:
            raise RuleViolation(f"'{sp_stage}' is not a valid SP stage")
        if sp_stage != "won" and body.stage not in ("closed_won", "closed_lost", "dropped", "on_hold"):
            try:
                rules_svc.validate_new_deal_stage(sp_stage, rules)
            except RuleViolation:
                if len((body.stage_override_reason or "").strip()) < 5:
                    raise
                data["todays_update"] = ((data.get("todays_update") or "") +
                                         f" [Started below SP5 — {body.stage_override_reason.strip()}]").strip()
        if sp_stage == "won":
            data["stage"] = "closed_won"
        elif data["stage"] == "closed_won":
            sp_stage = "won"
        data["sp_stage"] = sp_stage
        if data["stage"] == "closed_won":
            rules_svc.validate_won(body.won_basis, body.won_at or date.today())
            data["won_at"] = body.won_at or date.today()
        elif body.invoiced_at:
            raise RuleViolation("A tax invoice date can only be recorded on a won deal.")
        data["win_probability"] = rules_svc.resolve_win_probability(
            data["stage"], sp_stage, body.win_probability, rules)
        data["deal_value"] = rules_svc.derive_deal_value(
            body.recurring_revenue, body.one_time_revenue) if body.recurring_revenue is not None \
            or body.one_time_revenue is not None else body.deal_value
    except RuleViolation as e:
        raise HTTPException(422, str(e))
    if data.get("title"):
        data["title"] = data["title"].strip() or None
    data.pop("stage_override_reason", None)
    deal = PipelineDeal(user_id=user.id, **data)
    db.add(deal)
    await db.commit()
    if deal.stage == "closed_won":
        await _notify_finance(db, background_tasks, deal, user, rules)
    return {"id": str(deal.id), **{k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in data.items()}}


@router.get("/rules")
async def deal_rules(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """SP ladder with each stage's default win % and floor, plus the mandatory
    flags — the deal form reads this instead of hardcoding numbers (config:
    feature_flags 'deal_rules')."""
    rules = await rules_svc.get_rules(db)
    return {
        "stages": [{"key": k, "label": rules_svc.sp_stage_label(k), "default": v["default"], "floor": v["floor"],
                    "category": v.get("category")}
                   for k, v in rules["stages"].items()],
        "require_company_contact": rules["require_company_contact"],
        "require_revenue_split": rules["require_revenue_split"],
        "convert_min_stage": rules["convert_min_stage"],
        "deal_start_stage": rules["deal_start_stage"],
        "new_deal_min_stage": rules["new_deal_min_stage"],
        "forecast_categories": rules_svc.FORECAST_CATEGORY_LABELS,
    }


async def _notify_finance(db: AsyncSession, background_tasks: BackgroundTasks, deal: PipelineDeal,
                          owner: User, rules: dict):
    """Order booked -> tell Finance to invoice in the ERP (v1.6.0). Never blocks
    or fails the save: a missing recipient or SMTP just logs."""
    if not rules.get("notify_finance_on_won", True):
        return
    try:
        rows = (await db.execute(select(User.email).where(User.role == "finance", User.is_active == True))).all()  # noqa: E712
        to = [r[0] for r in rows if r[0]]
        if not to:
            return
        subject, html, text = fin_svc.build_won_notice(deal, owner.name)
        background_tasks.add_task(email_service.send_email, to, subject, html, text)
    except Exception:  # noqa: BLE001 - notification must never break a deal save
        pass


@router.get("/duplicates")
async def open_for_company(account_id: uuid.UUID, contact_id: Optional[uuid.UUID] = None,
                           db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """What is already open for this company (and contact)? Shown on the new
    lead / deal form as an alert; creating a parallel deal is always allowed."""
    deny_governance(user)
    from app.models import Lead
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    deals = (await db.execute(select(PipelineDeal).where(
        PipelineDeal.account_id == account_id, PipelineDeal.is_seed == False))).scalars().all()  # noqa: E712
    leads = (await db.execute(select(Lead).where(
        Lead.account_id == account_id, Lead.is_seed == False))).scalars().all()  # noqa: E712
    owner_ids = {d.user_id for d in deals} | {l.user_id for l in leads}
    names = {}
    if owner_ids:
        names = {uid: n for uid, n in (await db.execute(select(User.id, User.name).where(User.id.in_(owner_ids)))).all()}
    out = dup_svc.summarise(deals, leads, None if visible is None else set(visible), contact_id,
                            names, rules_svc.sp_stage_label)
    return out

async def _visible_deals_query(db: AsyncSession, user: User, include_archived: bool, include_seed: bool):
    """The one place that decides which deals a user may see (shared by the
    Pipeline list and the forecast sheet): governance blocked, owner scope via
    resolve_visible_user_ids, archived/seed excluded unless opted in."""
    deny_governance(user)
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    show_seed = include_seed and role_level(user.role) >= 40
    q = select(PipelineDeal)
    if visible is not None:
        q = q.where(PipelineDeal.user_id.in_(visible))
    if not include_archived:
        q = q.where(PipelineDeal.archived == False)
    if not show_seed:
        q = q.where(PipelineDeal.is_seed == False)
    return q.order_by(PipelineDeal.updated_at.desc())


def _ledger_label(stage: str, eta, note) -> Optional[str]:
    """Target label worth recording in the change ledger; None once closed or when unset."""
    if stage in sheet.CLOSED:
        return None
    lbl = sheet.target_label(stage, eta, note)
    return None if lbl == "—" else lbl


def _log_target_change(db: AsyncSession, deal: PipelineDeal, old: Optional[str], new: Optional[str],
                       user: User, reason: Optional[str] = None):
    if old and old != new:
        db.add(PipelineTargetChange(deal_id=deal.id, old_label=old, new_label=new,
                                    reason=(reason or None), changed_by=user.id,
                                    changed_at=datetime.utcnow()))


@router.get("")
async def list_deals(include_archived: bool = False, include_seed: bool = False,
                     db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Scoped the same way Opportunities already is: reps see their own
    deals, manager/regional_manager/business_head see their whole visible
    hierarchy via resolve_visible_user_ids (business_head = all regions in
    the business). This was hardcoded to user.id only - Pipeline was
    silently showing just the actor's own deals regardless of role, while
    Opportunities (same underlying `pipeline` table) showed the correct
    scoped set. That's why a Business Head's Pipeline view looked like a
    handful of personal deals instead of the whole BU.

    Archived deals are excluded by default for every scope — including
    scope="all" (ceo/coo/super_admin), where `visible is None` means no
    owner filter applies at all, so dummy/test deals left behind by
    deactivated accounts used to show up unfiltered. include_archived=true
    opts back in for admins who need to see what was archived.

    Seeded deals (seed_v3.py, see migration 0029) are excluded by default
    too — this is the actual working Pipeline screen, so it was arguably a
    worse leak than the analytics widgets fixed in the same pass: a manager
    scrolling their pipeline would see fake placeholder companies mixed in
    with real deals. include_seed=true opts back in, gated to business_head+
    (matching list_meetings()'s and loss_analysis()'s convention).

    Governance is blocked outright (deny_governance) rather than redacted
    field-by-field — deal_value appears on every row, and Pipeline isn't
    part of what governance validates (DSR/DMR/DOR/FGA) in the first
    place."""
    q = await _visible_deals_query(db, user, include_archived, include_seed)
    result = await db.execute(q)
    now = datetime.now(timezone.utc)
    rules = await rules_svc.get_rules(db)
    rows = []
    for d in result.scalars().all():
        row = {c.name: getattr(d, c.name) for c in d.__table__.columns}
        row["needs_revenue_split"] = rules_svc.needs_revenue_split(d)
        row["forecast_probability"] = rules_svc.forecast_probability(d, rules)
        row.update(rules_svc.deal_metrics(d, rules))      # v1.6.1: is_open / amount / win_pct / weighted_amount
        row["sp_stage_label"] = rules_svc.sp_stage_label(d.sp_stage) if d.sp_stage else None
        cat = rules_svc.forecast_category(d, rules)
        row["forecast_category"] = cat
        row["forecast_category_label"] = rules_svc.FORECAST_CATEGORY_LABELS.get(cat) if cat else None
        last_touch = _aware(d.last_activity_at) or _aware(d.created_at)
        days_since = (now - last_touch).days if last_touch else None
        row["days_since_activity"] = days_since
        row["is_stalled"] = bool(
            d.stage in OPEN_STAGES and days_since is not None and days_since >= STALL_THRESHOLD_DAYS
        )
        rows.append(row)
    return rows

@router.post("/{deal_id}/archive")
async def archive_deal(deal_id: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Soft-delete — never a hard DELETE, since deals feed revenue/win-loss/
    FGA history. Manager level and above, within their visible scope, so a
    business_head can clean up dummy/test deals under their own business
    without needing super_admin. Owner alone (a rep on their own deal) is
    NOT enough — accidental self-archival of a real deal would silently
    drop it from the rep's own Pipeline with no easy way to notice."""
    from app.services.permission_service import resolve_visible_user_ids
    if role_level(user.role) < 20:
        raise HTTPException(403, "Archiving requires Manager level or above")
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and deal.user_id not in visible:
        raise HTTPException(403, "You cannot archive a deal outside your scope")
    deal.archived = True
    deal.archived_at = datetime.now(timezone.utc)
    deal.archived_by = user.id
    await db.commit()
    return {"id": deal_id, "archived": True}

@router.post("/{deal_id}/unarchive")
async def unarchive_deal(deal_id: str, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    from app.services.permission_service import resolve_visible_user_ids
    if role_level(user.role) < 20:
        raise HTTPException(403, "Unarchiving requires Manager level or above")
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and deal.user_id not in visible:
        raise HTTPException(403, "You cannot unarchive a deal outside your scope")
    deal.archived = False
    deal.archived_at = None
    deal.archived_by = None
    await db.commit()
    return {"id": deal_id, "archived": False}

@router.patch("/{deal_id}")
async def update_deal(deal_id: str, body: DealIn, request: Request,
                      background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    result = await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")

    sent = body.model_fields_set
    # Only fields the client actually sent (an omitted `stage` used to fall back
    # to the model default "cold" and silently overwrite the deal's real stage).
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in sent}
    updates.pop("stage_override_reason", None)

    # ── v1.5.0 rules, checked on the merged (existing + sent) record ──────────
    rules = await rules_svc.get_rules(db)
    try:
        if {"account_id", "contact_id"} & sent:
            account, contact = await resolve_links(
                db, updates.get("account_id", deal.account_id),
                updates.get("contact_id", deal.contact_id), rules["require_company_contact"])
            if account is not None:
                updates["company"] = account.name
                updates["account_id"] = account.id
                updates["primary_contact"] = display_name(contact) or deal.primary_contact
                if contact is not None:
                    updates["contact_id"] = contact.id
        # SP "Won" and the legacy closed_won status are one thing: keep them in step.
        if updates.get("sp_stage") == "won":
            updates["stage"] = "closed_won"
        elif updates.get("stage") == "closed_won" and (updates.get("sp_stage") or deal.sp_stage):
            updates["sp_stage"] = "won"
        new_stage = updates.get("stage", deal.stage)
        new_sp = updates.get("sp_stage", deal.sp_stage)
        if new_sp is not None and new_sp not in rules["stages"]:
            raise RuleViolation(f"'{new_sp}' is not a valid SP stage")
        if new_stage == "closed_won" and deal.stage != "closed_won":
            # entering Won needs the customer's commitment on record
            rules_svc.validate_won(updates.get("won_basis", deal.won_basis),
                                   updates.get("won_at") or deal.won_at or date.today())
            updates.setdefault("won_at", deal.won_at or date.today())
        if updates.get("invoiced_at") and new_stage != "closed_won":
            raise RuleViolation("A tax invoice date can only be recorded on a won deal.")
        if new_sp is not None and new_sp != "won" and new_stage == "closed_won":
            updates["sp_stage"] = "won"; new_sp = "won"
        money_touched = {"recurring_revenue", "one_time_revenue", "deal_value", "stage", "sp_stage"} & sent
        if money_touched:
            rec = updates.get("recurring_revenue", deal.recurring_revenue)
            one = updates.get("one_time_revenue", deal.one_time_revenue)
            rules_svc.validate_revenue_split(
                None if rec is None else float(rec), None if one is None else float(one), new_stage, rules)
            if "recurring_revenue" in sent or "one_time_revenue" in sent:
                updates["deal_value"] = rules_svc.derive_deal_value(rec, one)
        sp_changed = "sp_stage" in updates and updates["sp_stage"] != deal.sp_stage
        if "win_probability" in sent or sp_changed or "stage" in sent:
            requested = (body.win_probability if "win_probability" in sent
                         else (None if sp_changed else deal.win_probability))
            win = rules_svc.resolve_win_probability(new_stage, new_sp, requested, rules)
            if win is not None:
                updates["win_probability"] = win
    except RuleViolation as e:
        raise HTTPException(422, str(e))

    # Capture value/stage changes specifically — these feed revenue forecasting,
    # so a change to them is worth an explicit audit entry.
    old_value = float(deal.deal_value) if deal.deal_value is not None else None
    old_stage = deal.stage
    old_target = _ledger_label(deal.stage, deal.closure_eta, deal.target_note)

    for k, v in updates.items():
        setattr(deal, k, v)
    _log_target_change(db, deal, old_target, _ledger_label(deal.stage, deal.closure_eta, deal.target_note), user)
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
    if old_stage != "closed_won" and deal.stage == "closed_won":
        await _notify_finance(db, background_tasks, deal, user, rules)

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
    # Required when outcome == closed_won: the customer's commitment.
    won_basis: Optional[Literal["email", "loi", "po", "agreement"]] = None
    won_at: Optional[date] = None
    won_ref: Optional[str] = Field(default=None, max_length=120)

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

    if body.outcome == "closed_won":
        try:
            rules_svc.validate_won(body.won_basis, body.won_at or date.today())
        except RuleViolation as e:
            raise HTTPException(422, str(e))
        deal.won_basis, deal.won_at, deal.won_ref = body.won_basis, body.won_at or date.today(), body.won_ref
        deal.win_probability = 100
        if deal.sp_stage:
            deal.sp_stage = "won"

    old_target = _ledger_label(deal.stage, deal.closure_eta, deal.target_note)
    deal.stage               = body.outcome
    _log_target_change(db, deal, old_target, _ledger_label(deal.stage, deal.closure_eta, deal.target_note), user)
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
    if body.outcome == "closed_won":
        await _notify_finance(db, background_tasks, deal, user, await rules_svc.get_rules(db))

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
async def loss_analysis(include_seed: bool = False,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Aggregate win-loss summary + AI pattern analysis across the caller's
    visible deals. Rep sees own; manager sees team.
    Archived and seeded deals (seed_v3.py, see migration 0029) are excluded
    by default — this is the same class of leakage fixed for DSR/Meetings in
    migration 0027; PipelineDeal was missed in that pass. include_seed=true
    opts back in for business_head+ verification, matching the convention
    used elsewhere (analytics.py, meetings.py)."""
    from app.models import role_level
    from app.services.permission_service import resolve_visible_user_ids
    from sqlalchemy import func

    if role_level(user.role) >= 20:
        visible = await resolve_visible_user_ids(db, user)
    else:
        visible = [user.id]
    show_seed = include_seed and role_level(user.role) >= 40

    q = select(PipelineDeal).where(PipelineDeal.archived == False)
    if not show_seed:
        q = q.where(PipelineDeal.is_seed == False)
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

    # Same ARR+One-time-with-deal_value-fallback fix as analytics.py/
    # scoring_engine.py/incentives.py (2026-10-23) — win/loss value here was
    # also undercounting any deal entered via Pipeline Sheet's ARR/One-time
    # fields instead of the legacy single deal_value field.
    from app.services.pipeline_sheet_service import amounts
    lost_value = sum(amounts(d.recurring_revenue, d.one_time_revenue, d.deal_value)["total"] for d in lost)
    won_value  = sum(amounts(d.recurring_revenue, d.one_time_revenue, d.deal_value)["total"] for d in won)
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
        PipelineDeal.archived == False,
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


# ── Forecast sheet (v1.5.0): rep-wise view, inline forecast edit, Excel export ──
class ForecastIn(BaseModel):
    win_probability: Optional[int] = Field(default=None, ge=0, le=100)
    closure_eta: Optional[date] = None
    target_note: Optional[str] = Field(default=None, max_length=60)
    reason: Optional[str] = Field(default=None, max_length=300)


@router.patch("/{deal_id}/forecast")
async def update_forecast(deal_id: str, body: ForecastIn, request: Request,
                          background_tasks: BackgroundTasks,
                          db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Edit only the forecast cells (win %, target month/note). A changed target is
    written to the ledger so the earlier month stays visible (struck through)."""
    deny_governance(user)
    deal = (await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    _check_deal_access(deal, user)
    sent = body.model_fields_set
    if "win_probability" in sent:
        try:
            deal.win_probability = rules_svc.resolve_win_probability(
                deal.stage, deal.sp_stage, body.win_probability, await rules_svc.get_rules(db))
        except RuleViolation as e:
            raise HTTPException(422, str(e))
    old_target = _ledger_label(deal.stage, deal.closure_eta, deal.target_note)
    if "closure_eta" in sent:
        deal.closure_eta = body.closure_eta
    if "target_note" in sent:
        deal.target_note = (body.target_note or "").strip() or None
    _log_target_change(db, deal, old_target, _ledger_label(deal.stage, deal.closure_eta, deal.target_note),
                       user, body.reason)
    deal.last_activity_at = datetime.utcnow()
    await db.commit()
    background_tasks.add_task(audit, db, user, "UPDATE", "pipeline", deal_id,
                              f"{deal.company}: forecast edited", request=request)
    return {"id": deal_id, "updated": True}


async def _sheet_data(db: AsyncSession, user: User, include_closed: bool, include_seed: bool, rep_id: Optional[str]):
    q = await _visible_deals_query(db, user, False, include_seed)
    if rep_id:
        q = q.where(PipelineDeal.user_id == rep_id)
    if not include_closed:
        q = q.where(PipelineDeal.stage.notin_(sorted(sheet.CLOSED)))
    deals = (await db.execute(q.order_by(PipelineDeal.created_at))).scalars().all()
    if not deals:
        return {"groups": [], "totals": sheet._sum([])}
    ids = [d.id for d in deals]
    hist: dict = {}
    for ch in (await db.execute(select(PipelineTargetChange).where(PipelineTargetChange.deal_id.in_(ids))
                                .order_by(PipelineTargetChange.changed_at))).scalars().all():
        hist.setdefault(ch.deal_id, []).append(ch.old_label)
    names = {u.id: u.name for u in (await db.execute(
        select(User).where(User.id.in_({d.user_id for d in deals})))).scalars().all()}
    items = [(str(d.user_id), names.get(d.user_id, "Unassigned"), sheet.build_row(d, hist.get(d.id, [])))
             for d in deals]
    return sheet.group_by_rep(items)


@router.get("/sheet")
async def pipeline_sheet(include_closed: bool = True, include_seed: bool = False, rep_id: Optional[str] = None,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await _sheet_data(db, user, include_closed, include_seed, rep_id)


@router.get("/sheet.xlsx", dependencies=[Depends(export_guard("Pipeline sheet (xlsx)"))])
async def pipeline_sheet_xlsx(include_closed: bool = True, include_seed: bool = False, rep_id: Optional[str] = None,
                              db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from fastapi.responses import Response
    from app.services.pipeline_sheet_export import build_xlsx
    data = await _sheet_data(db, user, include_closed, include_seed, rep_id)
    return Response(content=build_xlsx(data),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="pipeline-{date.today().isoformat()}.xlsx"'})
