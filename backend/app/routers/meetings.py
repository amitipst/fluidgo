from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import Meeting, Lead
from app.services.deps import get_current_user
from app.services.rigor_service import bant_score, score_lead
from app.services.audit_service import audit
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


# ── Convert a meeting → lead (funnel step 1) ──────────────────────────────────
class ConvertMeetingIn(BaseModel):
    # Optional overrides — if omitted, we carry the meeting's own data forward.
    requirement:      Optional[str]  = None
    next_action:      Optional[str]  = None
    next_action_date: Optional[date] = None
    source:           Optional[str]  = None  # defaults from meeting_type

@router.post("/{meeting_id}/convert-to-lead")
async def convert_meeting_to_lead(
    meeting_id: str,
    body: ConvertMeetingIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Promote a meeting to a Lead, carrying company/contact/discussion forward
    (no re-typing). Idempotent-safe: a meeting already converted returns 400 with
    the existing lead id rather than creating a duplicate."""
    m = (await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Meeting not found")
    if m.user_id != user.id:
        # Managers can view team meetings, but converting is the owner's action
        raise HTTPException(403, "Only the meeting owner can convert it to a lead")
    if m.converted_to_lead_id:
        raise HTTPException(400, "This meeting has already been converted to a lead.")

    # Map meeting_type → lead source
    src = body.source or {"Call": "Call", "Virtual": "LinkedIn", "F2F": "Visit"}.get(m.meeting_type, "Call")

    lead = Lead(
        user_id=user.id,
        date=date.today(),
        company=m.company,
        contact_name=m.contact_name,
        requirement=body.requirement or m.discussion or m.support_needed,
        source=src if src in ("Call", "Visit", "Referral", "LinkedIn", "Email") else "Call",
        next_action=body.next_action,
        next_action_date=body.next_action_date,
        status="new",
        source_meeting_id=m.id,
    )
    lead.ai_lead_score = score_lead(lead)
    db.add(lead)
    await db.flush()

    # Mark the meeting converted (so the UI shows ✓ instead of Convert again)
    m.status = "converted"
    m.converted_to_lead_id = lead.id
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "CONVERT_TO_LEAD", "meeting", meeting_id,
        f"{m.company}: meeting → lead ({lead.id})", request=request
    )
    return {"lead_id": str(lead.id), "company": lead.company,
            "ai_lead_score": lead.ai_lead_score,
            "message": f"'{m.company}' converted to a lead."}
