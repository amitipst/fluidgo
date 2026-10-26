from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import Lead, PipelineDeal, User, ROLE_HIERARCHY, role_level
from app.services.deps import get_current_user
from app.services.rigor_service import score_lead
from app.services.audit_service import audit
from app.services import lead_stage_service
from app.services import deal_rules_service as rules_svc
from app.services.deal_rules_service import RuleViolation
from app.services.crm_link_service import resolve_links, display_name

router = APIRouter()


# ── SPANCO stage ladder (config-driven — see lead_stage_service) ────────────
@router.get("/stages")
async def get_lead_stages(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Canonical Leads SPANCO stage ladder + whether the Kanban board is
    switched on. The frontend fetches this instead of hardcoding a stage
    list — see lead_stage_service module docstring for why, and
    Amit's 2026-10-24 'right SPANCO' handoff for where the default ladder
    came from."""
    stages = await lead_stage_service.get_lead_stages(db)
    kanban_enabled = await lead_stage_service.is_kanban_enabled(db)
    return {"stages": stages, "kanban_enabled": kanban_enabled}


class UpdateLeadStageIn(BaseModel):
    stage: str


@router.patch("/{lead_id}/stage")
async def update_lead_stage(lead_id: str, body: UpdateLeadStageIn, request: Request,
                            background_tasks: BackgroundTasks,
                            db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """Move a lead to a different SPANCO stage — the Kanban board's drag/tap
    action, or the detail view. Visibility mirrors reassign_lead() exactly
    (own lead, or scope="all") rather than inventing a new permission rule."""
    lead = (await db.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))).scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")

    is_org_wide = ROLE_HIERARCHY.get(user.role, {}).get("scope") == "all"
    if not is_org_wide and lead.user_id != user.id:
        raise HTTPException(403, "You cannot move this lead")

    stages = await lead_stage_service.get_lead_stages(db)
    if not lead_stage_service.is_valid_stage_key(body.stage, stages):
        raise HTTPException(422, f"'{body.stage}' is not a valid stage")

    old_stage = lead.stage
    lead.stage = body.stage
    await db.commit()

    if old_stage != body.stage:
        background_tasks.add_task(
            audit, db, user, "STAGE_CHANGE", "lead", lead_id,
            f"{lead.company}: {old_stage or '(none)'} → {body.stage}", request=request,
        )
    return {"id": lead_id, "stage": body.stage}

class LeadIn(BaseModel):
    date: date
    # v1.5.0 company-first: pick (or add) the company and contact in the
    # Contacts master, then the lead is created against them. `company` /
    # `contact_name` stay as display text and are filled from the master.
    account_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    company: Optional[str] = None
    contact_name: Optional[str] = None
    requirement: Optional[str] = None
    source: Literal["Call", "Visit", "Referral", "LinkedIn", "Email"] = "Call"
    next_action: Optional[str] = None
    next_action_date: Optional[date] = None

@router.post("")
async def create_lead(body: LeadIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rules = await rules_svc.get_rules(db)
    try:
        account, contact = await resolve_links(
            db, body.account_id, body.contact_id, rules["require_company_contact"])
    except RuleViolation as e:
        raise HTTPException(422, str(e))
    data = body.model_dump()
    if account is not None:
        data["company"] = account.name
        data["contact_name"] = display_name(contact) or data.get("contact_name")
    if not (data.get("company") or "").strip():
        raise HTTPException(422, "Company is required.")
    lead = Lead(user_id=user.id, **data)
    lead.ai_lead_score = score_lead(lead)
    db.add(lead)
    await db.commit()
    return {"id": str(lead.id), "ai_lead_score": lead.ai_lead_score,
            **{k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in data.items()}}

@router.get("")
async def list_leads(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Own-only for everyone below scope="all" — unlike list_deals()/
    list_meetings(), this endpoint never grew a manager/team-scope tier, and
    that gap is left as-is here (not this pass's problem to solve).
    scope="all" roles (coo/ceo/super_admin/governance/crm_admin) DO see every
    rep's leads org-wide — the same reach resolve_visible_user_ids already
    gives them on Pipeline/Meetings/DSR; Leads was simply the one place that
    rule hadn't been applied yet, surfaced by the 2026-10-22 crm_admin ask
    ("see the leads of all people"). Seeded leads (seed_v3.py, see migration
    0029) are excluded unconditionally either way, same reasoning as
    dsr.py's /history."""
    is_org_wide = ROLE_HIERARCHY.get(user.role, {}).get("scope") == "all"
    query = select(Lead).where(Lead.is_seed == False)
    if not is_org_wide:
        query = query.where(Lead.user_id == user.id)
    result = await db.execute(query.order_by(Lead.date.desc()))
    return [{c.name: getattr(l, c.name) for c in l.__table__.columns} for l in result.scalars().all()]


class ReassignLeadIn(BaseModel):
    new_owner_id: str


@router.post("/{lead_id}/reassign")
async def reassign_lead(lead_id: str, body: ReassignLeadIn, request: Request,
                        background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Change a lead's owner — mirrors pipeline.py's reassign_deal exactly
    (same manager-tier+ gate, same visible-scope check on both the current
    and new owner). Built for crm_admin (scope="all", so both checks below
    are a no-op for it — every lead/user is in its visible scope) but not
    restricted to it: any manager-tier+ role already relies on the same
    pattern elsewhere, so there's no reason to special-case this endpoint
    to one role."""
    if role_level(user.role) < 20:
        raise HTTPException(403, "Only managers and above can reassign leads")

    lead = (await db.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))).scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")

    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and lead.user_id not in visible:
        raise HTTPException(403, "You cannot reassign this lead")

    new_owner_id = uuid.UUID(body.new_owner_id)
    new_owner = (await db.execute(select(User).where(User.id == new_owner_id))).scalar_one_or_none()
    if not new_owner:
        raise HTTPException(404, "New owner not found")
    if visible is not None and new_owner_id not in visible:
        raise HTTPException(403, "You cannot assign this lead to someone outside your scope")

    old_owner_id = lead.user_id
    lead.user_id = new_owner_id
    await db.commit()

    if old_owner_id != new_owner_id:
        background_tasks.add_task(
            audit, db, user, "REASSIGN", "lead", lead_id,
            f"{lead.company}: reassigned to {new_owner.name}", request=request,
        )
    return {"id": lead_id, "new_owner_id": str(new_owner_id), "message": f"Lead reassigned to {new_owner.name}."}


# ── Convert a lead → pipeline deal / opportunity (funnel step 2) ──────────────
class ConvertLeadIn(BaseModel):
    deal_value:    Optional[float] = None   # legacy; ignored when ARR/One-time are sent
    recurring_revenue: Optional[float] = None   # ARR
    one_time_revenue:  Optional[float] = None
    win_probability:   Optional[int]   = None
    sp_stage:      Optional[str]   = None
    account_id:    Optional[uuid.UUID] = None
    contact_id:    Optional[uuid.UUID] = None
    stage:         str = "qualification"
    closure_eta:   Optional[date]  = None
    next_step:     Optional[str]   = None
    solution_area: Optional[str]   = None
    title:         Optional[str]   = None   # v1.6.0 deal name (defaults from the requirement)
    # Escape hatch (best practice: friction with accountability, not a dead end).
    # A rep who must convert a lead that has not reached the gate stage gives a
    # reason; it is audited and the deal opens at the lead's own stage floor.
    override_reason: Optional[str] = None

@router.post("/{lead_id}/convert-to-deal")
async def convert_lead_to_deal(
    lead_id: str,
    body: ConvertLeadIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Promote a qualified lead to a Pipeline deal (Opportunity), carrying
    company/contact/requirement forward. Blocks double-conversion."""
    lead = (await db.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))).scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.user_id != user.id:
        raise HTTPException(403, "Only the lead owner can convert it to a deal")
    if lead.converted_to_deal_id:
        raise HTTPException(400, "This lead has already been converted to a pipeline deal.")

    rules = await rules_svc.get_rules(db)
    stage = body.stage or "qualification"
    try:
        account, contact = await resolve_links(
            db, body.account_id or lead.account_id, body.contact_id or lead.contact_id,
            rules["require_company_contact"])
        recurring, one_time = body.recurring_revenue, body.one_time_revenue
        rules_svc.validate_revenue_split(recurring, one_time, stage, rules)
        overridden = False
        try:
            rules_svc.validate_convert(lead.stage, rules)
        except RuleViolation:
            if len((body.override_reason or "").strip()) < 5 or lead.stage in rules_svc.LEAD_EXIT_STAGES:
                raise
            overridden = True
        sp_stage = body.sp_stage or rules_svc.deal_start_stage(lead.stage, rules)
        if sp_stage not in rules["stages"] or sp_stage == "won":
            raise RuleViolation(f"'{sp_stage}' is not a valid SP stage")
        win = rules_svc.resolve_win_probability(stage, sp_stage, body.win_probability, rules)
    except RuleViolation as e:
        raise HTTPException(422, str(e))

    deal = PipelineDeal(
        user_id=user.id,
        company=account.name if account else lead.company,
        title=((body.title or lead.requirement or "").strip()[:150] or None),
        account_id=account.id if account else lead.account_id,
        contact_id=contact.id if contact else lead.contact_id,
        stage=stage,
        sp_stage=sp_stage,
        primary_contact=display_name(contact) or lead.contact_name,
        todays_update=f"Converted from lead. Requirement: {lead.requirement or 'n/a'}",
        next_step=body.next_step or lead.next_action,
        closure_eta=body.closure_eta,
        recurring_revenue=recurring,
        one_time_revenue=one_time,
        deal_value=rules_svc.derive_deal_value(recurring, one_time),
        win_probability=win,
        solution_area=body.solution_area,
        source_lead_id=lead.id,
    )
    db.add(deal)
    await db.flush()

    lead.status = "converted"
    lead.converted_to_deal_id = deal.id
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "CONVERT_TO_DEAL", "lead", lead_id,
        f"{lead.company}: lead → pipeline deal ({deal.id})"
        + (f" [gate override: {body.override_reason.strip()}]" if overridden else ""), request=request
    )
    return {"deal_id": str(deal.id), "company": deal.company,
            "message": f"'{lead.company}' converted to a pipeline deal."}
