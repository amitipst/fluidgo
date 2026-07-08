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
async def list_meetings(
    scope: Literal["mine", "team"] = "mine",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """scope=mine → only the caller's own meetings (default).
    scope=team → all meetings across the caller's visible users (managers+).
    Field roles always get their own regardless of scope."""
    from app.models import role_level
    if scope == "team" and role_level(user.role) >= 20:
        from app.services.permission_service import resolve_visible_user_ids
        visible = await resolve_visible_user_ids(db, user)
        q = select(Meeting).order_by(Meeting.date.desc())
        if visible is not None:
            q = q.where(Meeting.user_id.in_(visible))
    else:
        q = select(Meeting).where(Meeting.user_id == user.id).order_by(Meeting.date.desc())
    result = await db.execute(q)
    meetings = result.scalars().all()
    out = []
    # Resolve rep names once for team view
    name_map = {}
    if scope == "team":
        user_ids = {m.user_id for m in meetings}
        if user_ids:
            reps = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
            name_map = {u.id: u.name for u in reps}
    for m in meetings:
        d = {c.name: getattr(m, c.name) for c in m.__table__.columns}
        d["bant"] = bant_score(m)
        if scope == "team":
            d["rep_name"] = name_map.get(m.user_id, "Unknown")
        out.append(d)
    return out
