from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import Meeting
from app.services.deps import get_current_user
from app.services.rigor_service import bant_score
from app.models import User

router = APIRouter()

class MeetingIn(BaseModel):
    date: date
    company: str
    contact_name: Optional[str] = None
    meeting_type: Literal["F2F", "Virtual", "Call"] = "F2F"
    discussion: Optional[str] = None
    opportunity: bool = False
    support_needed: Optional[str] = None
    bant_budget: Optional[bool] = None
    bant_authority: Optional[bool] = None
    bant_need: Optional[bool] = None
    bant_timeline: Optional[bool] = None

@router.post("")
async def create_meeting(body: MeetingIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    m = Meeting(user_id=user.id, **body.model_dump())
    db.add(m)
    await db.flush()
    bs = bant_score(m)
    m.ai_intent_score = bs["intent"]
    m.ai_closure_pct = bs["closure_pct"]
    await db.commit()
    return {**body.model_dump(), "id": str(m.id), "bant": bs}

@router.get("")
async def list_meetings(db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Meeting).where(Meeting.user_id == user.id).order_by(Meeting.date.desc())
    )
    meetings = result.scalars().all()
    out = []
    for m in meetings:
        d = {c.name: getattr(m, c.name) for c in m.__table__.columns}
        d["bant"] = bant_score(m)
        out.append(d)
    return out
