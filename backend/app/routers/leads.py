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

router = APIRouter()

class LeadIn(BaseModel):
    date: date
    company: str
    contact_name: Optional[str] = None
    requirement: Optional[str] = None
    source: Literal["Call", "Visit", "Referral", "LinkedIn", "Email"] = "Call"
    next_action: Optional[str] = None
    next_action_date: Optional[date] = None

@router.post("")
async def create_lead(body: LeadIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    lead = Lead(user_id=user.id, **body.model_dump())
    lead.ai_lead_score = score_lead(lead)
    db.add(lead)
    await db.commit()
    return {"id": str(lead.id), "ai_lead_score": lead.ai_lead_score, **body.model_dump()}

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
    deal_value:    Optional[float] = None
    stage:         str = "qualification"
    closure_eta:   Optional[date]  = None
    next_step:     Optional[str]   = None
    solution_area: Optional[str]   = None

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

    deal = PipelineDeal(
        user_id=user.id,
        company=lead.company,
        stage=body.stage or "qualification",
        primary_contact=lead.contact_name,
        todays_update=f"Converted from lead. Requirement: {lead.requirement or 'n/a'}",
        next_step=body.next_step or lead.next_action,
        closure_eta=body.closure_eta,
        deal_value=body.deal_value,
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
        f"{lead.company}: lead → pipeline deal ({deal.id})", request=request
    )
    return {"deal_id": str(deal.id), "company": deal.company,
            "message": f"'{lead.company}' converted to a pipeline deal."}
