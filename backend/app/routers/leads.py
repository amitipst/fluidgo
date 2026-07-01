from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional, Literal
from app.database import get_db
from app.models import Lead, PipelineDeal, User
from app.services.deps import get_current_user
from app.services.rigor_service import score_lead

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
