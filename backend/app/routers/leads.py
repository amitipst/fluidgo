from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import Lead, PipelineDeal, User
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
    result = await db.execute(select(Lead).where(Lead.user_id == user.id).order_by(Lead.date.desc()))
    return [{c.name: getattr(l, c.name) for c in l.__table__.columns} for l in result.scalars().all()]


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
