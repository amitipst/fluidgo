from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import Meeting, Lead, DSRDaily, DORDaily
from app.services.deps import get_current_user, deny_governance
from app.services.rigor_service import bant_score, score_lead
from app.services.audit_service import audit
from app.services.account_service import get_or_create_account
from app.services import ai_service
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
    # ── CSG Phase 2 ─────────────────────────────────────────────────────────
    source: Literal["sales", "service_delivery"] = "sales"
    meeting_purpose: Optional[str] = None  # defaults per-source below if omitted
    attendees: Optional[list] = None

@router.post("")
async def create_meeting(body: MeetingIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """CSG Phase 2 — beyond creating the meeting row, resolves the Account
    this meeting belongs to (same get_or_create_account() DOR's
    flag-opportunity already uses) and links back to that day's DSR (source=
    sales) or DOR (source=service_delivery) row, if one exists yet. Doesn't
    force-create an empty DSR/DOR just to attach a meeting to it — DSR/DOR
    have their own independent submission workflow.

    Governance never logs a meeting — it's a validation-only role with no
    approval or authoring authority anywhere else in this codebase (see
    deny_governance() design note in deps.py); this endpoint had no role
    gate at all until now, which is the one place that principle wasn't
    enforced."""
    deny_governance(user)
    data = body.model_dump()
    if not data.get("meeting_purpose"):
        data["meeting_purpose"] = "sales_discovery" if body.source == "sales" else "delivery_review"

    account = await get_or_create_account(db, body.company, business=user.business or "fluidpro")

    dsr_id = None
    dor_id = None
    if body.source == "sales":
        dsr = (await db.execute(select(DSRDaily).where(
            DSRDaily.user_id == user.id, DSRDaily.date == body.date))).scalar_one_or_none()
        dsr_id = dsr.id if dsr else None
    else:
        dor = (await db.execute(select(DORDaily).where(
            DORDaily.user_id == user.id, DORDaily.report_date == body.date))).scalar_one_or_none()
        dor_id = dor.id if dor else None

    m = Meeting(user_id=user.id, account_id=account.id, dsr_id=dsr_id, dor_id=dor_id, **data)
    db.add(m)
    await db.flush()
    # BANT is a Sales pipeline-qualification concept — skip it for Delivery
    # meetings (QBR/cadence/escalation review) rather than showing a
    # meaningless "cold" score on something that was never a sales call.
    bs = None
    if body.source == "sales":
        bs = bant_score(m)
        m.ai_intent_score = bs["intent"]
        m.ai_closure_pct = bs["closure_pct"]
    await db.commit()
    return {**data, "id": str(m.id), "account_id": str(account.id),
            "dsr_id": str(dsr_id) if dsr_id else None,
            "dor_id": str(dor_id) if dor_id else None, "bant": bs}

@router.get("")
async def list_meetings(
    scope: Literal["mine", "team"] = "mine",
    include_seed: bool = False,
    dsr_id: Optional[str] = None,
    dor_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """scope=mine → only the caller's own meetings (default).
    scope=team → all meetings across the caller's visible users (managers+).
    Field roles always get their own regardless of scope.
    Seeded meetings (seed_v3.py, dated before the 2026-07-04 go-live —
    see migration 0027) are excluded by default; include_seed=true opts
    back in for business_head+ only.
    dsr_id/dor_id (CSG Phase 2): filter to meetings linked to one specific
    DSR/DOR row — this is how the DSR/DOR detail view shows "which meetings
    actually back this count" instead of a bare unverified number. Reuses
    this endpoint rather than adding a parallel one."""
    from app.models import role_level
    show_seed = include_seed and role_level(user.role) >= 40
    if scope == "team" and role_level(user.role) >= 20:
        from app.services.permission_service import resolve_visible_user_ids
        visible = await resolve_visible_user_ids(db, user)
        q = select(Meeting).order_by(Meeting.date.desc())
        if visible is not None:
            q = q.where(Meeting.user_id.in_(visible))
    else:
        q = select(Meeting).where(Meeting.user_id == user.id).order_by(Meeting.date.desc())
    if not show_seed:
        q = q.where(Meeting.is_seed == False)
    if dsr_id:
        q = q.where(Meeting.dsr_id == uuid.UUID(dsr_id))
    if dor_id:
        q = q.where(Meeting.dor_id == uuid.UUID(dor_id))
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
        d["bant"] = bant_score(m) if m.source == "sales" else None
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


# ── CSG Phase 2 — AI MOM Generator ────────────────────────────────────────────
async def _get_meeting_or_404(meeting_id: str, db: AsyncSession, user: User) -> Meeting:
    m = (await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))).scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Meeting not found")
    if m.user_id != user.id:
        from app.models import role_level
        from app.services.permission_service import resolve_visible_user_ids
        if role_level(user.role) < 20:
            raise HTTPException(403, "Not your meeting")
        visible = await resolve_visible_user_ids(db, user)
        if visible is not None and m.user_id not in visible:
            raise HTTPException(403, "Not visible to you")
    return m


@router.post("/{meeting_id}/generate-mom")
async def generate_mom(meeting_id: str, request: Request, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Generates a Minutes of Meeting from the meeting's notes (`discussion`)
    via the same Ollama call pattern as deal_momentum/daily_insight
    (app.services.ai_service). Output is markdown, not structured JSON — see
    the comment on Meeting.ai_mom_summary in models/__init__.py for why.
    Re-running this overwrites the previous AI draft; once a human edits or
    finalizes it (see PATCH .../mom below) that's a deliberate action, not
    something this endpoint should silently clobber — callers should check
    mom_status before calling this again.

    Governance is a viewer only (deny_governance) — _get_meeting_or_404's
    org-wide visibility for scope="all" roles previously let governance
    reach this write action too; that's the gap this call closes."""
    deny_governance(user)
    m = await _get_meeting_or_404(meeting_id, db, user)
    if not m.discussion or not m.discussion.strip():
        raise HTTPException(400, "This meeting has no notes to generate a MOM from — add discussion notes first.")

    context = (
        f"Company: {m.company}\n"
        f"Meeting purpose: {m.meeting_purpose or 'not specified'}\n"
        f"Meeting type: {m.meeting_type}\n"
        f"Attendees: {m.attendees if m.attendees else 'not listed'}\n"
        f"Notes:\n{m.discussion}"
    )
    summary = await ai_service.analyse(context, prompt_type="meeting_mom")
    m.ai_mom_summary = summary
    m.ai_mom_generated_at = datetime.utcnow()
    m.mom_status = "generated"
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "GENERATE_MOM", "meeting", meeting_id,
        f"{m.company}: AI MOM generated", request=request
    )
    return {"id": str(m.id), "ai_mom_summary": summary,
            "ai_mom_generated_at": m.ai_mom_generated_at.isoformat(), "mom_status": m.mom_status}


class MomUpdateIn(BaseModel):
    ai_mom_summary: str
    finalize: bool = False  # True → mom_status="finalized"; False → "edited"


@router.patch("/{meeting_id}/mom")
async def update_mom(meeting_id: str, body: MomUpdateIn, request: Request, background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Human review/correction checkpoint for the AI draft — required before
    an AI-generated MOM should be treated as authoritative (Constitution: AI
    output must be validated before it's acted on).

    Governance is a viewer only — see generate_mom's deny_governance note."""
    deny_governance(user)
    m = await _get_meeting_or_404(meeting_id, db, user)
    m.ai_mom_summary = body.ai_mom_summary
    m.mom_status = "finalized" if body.finalize else "edited"
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "UPDATE_MOM", "meeting", meeting_id,
        f"{m.company}: MOM {m.mom_status}", request=request
    )
    return {"id": str(m.id), "mom_status": m.mom_status}
