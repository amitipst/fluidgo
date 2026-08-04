from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal, List
import uuid
from app.database import get_db
from app.config import settings
from app.models import Meeting, Lead, DSRDaily, DORDaily, MeetingMomRevision
from app.services.deps import get_current_user, deny_governance
from app.services.rigor_service import bant_score, score_lead
from app.services.audit_service import audit
from app.services.account_service import get_or_create_account
from app.services import ai_service, email_service
from app.services import mom_export_service as export_svc
from app.models import User

router = APIRouter()


# ── MOM extension — attendees (grown) + discussion points (new) ──────────────
# migration 0032. JSONB is schemaless so neither needed DDL for the shape
# change — validation lives here, at the Pydantic boundary, matching this
# codebase's existing convention (nullable-with-default at the DB layer,
# enforcement at the API layer). See fluidgo-mom-architecture-lld.md §3.1/3.2.
class Attendee(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    title: Optional[str] = None
    side: Literal["us", "customer"]
    # Legacy field from the pre-0032 shape — kept so anything still reading
    # it doesn't break; _normalize_attendees() derives it from `side` at
    # both write and read time, callers never need to set it themselves.
    is_external: Optional[bool] = None


class DiscussionPoint(BaseModel):
    point: str
    responsibility_side: Literal["us", "customer"]
    responsibility_name: str
    # Plain ISO string (YYYY-MM-DD), not a `date` type — this column is
    # JSONB, and a python date object doesn't round-trip through it as
    # cleanly as through a real Date column; keeping it a string here
    # sidesteps that entirely and matches what a frontend date input
    # naturally produces anyway.
    target_date: Optional[str] = None
    status: Literal["open", "done", "slipped"] = "open"


def _normalize_attendees(raw: Optional[list]) -> Optional[list]:
    """Derives `side`/`is_external` for each other from whichever one is
    present. Handles both directions: new writes (Attendee requires `side`,
    may omit `is_external`) and old rows written before migration 0032
    (only had {name, title, is_external}, no `side`/`email` at all)."""
    if not raw:
        return raw
    out = []
    for a in raw:
        a = dict(a)
        if not a.get("side"):
            a["side"] = "customer" if a.get("is_external") else "us"
        if a.get("is_external") is None:
            a["is_external"] = a["side"] == "customer"
        out.append(a)
    return out


def _format_discussion_points(points: Optional[list]) -> str:
    """Renders the structured discussion_points list into the AI context
    string that generate_mom() feeds to meeting_mom.txt. Returns "" (no
    line at all) when there are none, so older meetings without this field
    read exactly as they did before migration 0032 — the prompt is written
    to work from free-text notes alone in that case.

    Kept as a plain readable line-per-point block (not raw JSON/dict repr)
    because phi3:mini follows a labeled list far more reliably than it
    parses a Python dict literal — see the "Structured discussion points"
    handling in meeting_mom.txt, which expects this exact heading string."""
    if not points:
        return ""
    lines = ["Structured discussion points (owner, due date, status):"]
    for p in points:
        point = p.get("point", "")
        owner = p.get("responsibility_name") or "Unassigned"
        side = p.get("responsibility_side")
        owner_label = f"{owner} ({side})" if side else owner
        due = p.get("target_date") or "no date set"
        status = p.get("status", "open")
        lines.append(f"- {point} - owner: {owner_label}, due {due}, status: {status}")
    return "\n".join(lines) + "\n"


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
    attendees: Optional[List[Attendee]] = None
    discussion_points: Optional[List[DiscussionPoint]] = None

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
    data["attendees"] = _normalize_attendees(data.get("attendees"))

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
        d["attendees"] = _normalize_attendees(d.get("attendees"))
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


def _serialize_meeting_detail(m: Meeting) -> dict:
    d = {c.name: getattr(m, c.name) for c in m.__table__.columns}
    d["attendees"] = _normalize_attendees(d.get("attendees"))
    d["bant"] = bant_score(m) if m.source == "sales" else None
    return d


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Single meeting, full detail — the /meetings/:id detail page's data
    source (list_meetings only returns the list-card fields today). Same
    visibility check as every other per-meeting action, including
    governance: read-only, org-wide is fine here — Meeting carries no money
    field to redact (unlike DSR/DOR's proposal_value), so unlike
    _serialize_dsr there's no viewer_role stripping needed, just the same
    _get_meeting_or_404 gate everything else already uses."""
    m = await _get_meeting_or_404(meeting_id, db, user)
    d = _serialize_meeting_detail(m)
    # The detail page header shows "logged by {rep_name}" (UIUX spec §4.1) —
    # list_meetings already resolves this for scope=team via a name_map;
    # this is the single-row equivalent (one extra query, not a batch, since
    # this endpoint only ever fetches one meeting at a time).
    rep = (await db.execute(select(User).where(User.id == m.user_id))).scalar_one_or_none()
    d["rep_name"] = rep.name if rep else "Unknown"
    return d


class MeetingPatchIn(BaseModel):
    attendees: Optional[List[Attendee]] = None
    discussion_points: Optional[List[DiscussionPoint]] = None


@router.patch("/{meeting_id}")
async def patch_meeting(meeting_id: str, body: MeetingPatchIn, request: Request,
                         background_tasks: BackgroundTasks,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Partial update for the structured minutes fields (attendees,
    discussion points) — deliberately separate from PATCH .../mom below,
    which is the AI-generated summary text, a different concern. Only
    fields actually provided change. Writes a meeting_mom_revisions row per
    changed field group — this is what makes "update the minutes in the
    tracker" mean something a governance viewer can actually see, not just
    a silent overwrite (ADR-2, fluidgo-mom-architecture-lld.md).

    Governance is a viewer only — see generate_mom's deny_governance note."""
    deny_governance(user)
    m = await _get_meeting_or_404(meeting_id, db, user)

    if body.attendees is not None:
        before = m.attendees
        after = _normalize_attendees([a.model_dump() for a in body.attendees])
        m.attendees = after
        db.add(MeetingMomRevision(meeting_id=m.id, actor_id=user.id,
                                   action="attendees_updated", before=before, after=after))

    if body.discussion_points is not None:
        before = m.discussion_points
        after = [p.model_dump() for p in body.discussion_points]
        m.discussion_points = after
        db.add(MeetingMomRevision(meeting_id=m.id, actor_id=user.id,
                                   action="discussion_points_updated", before=before, after=after))

    await db.commit()
    background_tasks.add_task(
        audit, db, user, "UPDATE_MEETING", "meeting", meeting_id,
        f"{m.company}: attendees/discussion points updated", request=request
    )
    return _serialize_meeting_detail(m)


@router.get("/{meeting_id}/revisions")
async def list_meeting_revisions(meeting_id: str, db: AsyncSession = Depends(get_db),
                                  user: User = Depends(get_current_user)):
    """Newest first. Same visibility check as the meeting itself, governance
    included — this IS the point of governance's read access into Meetings:
    confirming records actually get kept current over time, not just
    looking at whatever the latest state happens to be."""
    m = await _get_meeting_or_404(meeting_id, db, user)
    result = await db.execute(
        select(MeetingMomRevision)
        .where(MeetingMomRevision.meeting_id == m.id)
        .order_by(MeetingMomRevision.created_at.desc())
    )
    revisions = result.scalars().all()
    actor_ids = {r.actor_id for r in revisions}
    names = {}
    if actor_ids:
        actors = (await db.execute(select(User).where(User.id.in_(actor_ids)))).scalars().all()
        names = {a.id: a.name for a in actors}
    return [{
        "id": str(r.id), "action": r.action,
        "actor_name": names.get(r.actor_id, "Unknown"),
        "before": r.before, "after": r.after,
        "created_at": r.created_at.isoformat(),
    } for r in revisions]


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
        f"{_format_discussion_points(m.discussion_points)}"
        f"Notes:\n{m.discussion}"
    )
    before_summary = m.ai_mom_summary
    summary = await ai_service.analyse(context, prompt_type="meeting_mom")
    m.ai_mom_summary = summary
    m.ai_mom_generated_at = datetime.utcnow()
    m.mom_status = "generated"
    db.add(MeetingMomRevision(meeting_id=m.id, actor_id=user.id, action="generated",
                               before={"ai_mom_summary": before_summary},
                               after={"ai_mom_summary": summary}))
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
    before_summary = m.ai_mom_summary
    m.ai_mom_summary = body.ai_mom_summary
    m.mom_status = "finalized" if body.finalize else "edited"
    db.add(MeetingMomRevision(meeting_id=m.id, actor_id=user.id, action=m.mom_status,
                               before={"ai_mom_summary": before_summary},
                               after={"ai_mom_summary": body.ai_mom_summary}))
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "UPDATE_MOM", "meeting", meeting_id,
        f"{m.company}: MOM {m.mom_status}", request=request
    )
    return {"id": str(m.id), "mom_status": m.mom_status}


# ── Export & Send-to-Customer (2026-08-04) ────────────────────────────────────
@router.get("/{meeting_id}/export")
async def export_meeting(meeting_id: str, format: Literal["xlsx", "pdf", "docx"] = "pdf",
                          db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Downloads the minutes in the requested format — one canonical document
    assembled once (mom_export_service.build_minutes_document), three thin
    renderers so the formats can't drift out of sync with each other.
    Read-only — governance included, downloading isn't writing."""
    m = await _get_meeting_or_404(meeting_id, db, user)
    render_fn, mimetype, ext = export_svc.EXPORT_RENDERERS[format]
    doc = export_svc.build_minutes_document(m)
    content = render_fn(doc)
    filename = f"MOM_{m.company.replace(' ', '_')}_{m.date}.{ext}"
    return StreamingResponse(
        iter([content]), media_type=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_send_body(doc) -> tuple[str, str]:
    text = (
        f"Minutes of Meeting — {doc.company} ({doc.date})\n\n"
        f"{doc.ai_mom_summary or '(no summary generated yet — see attached document for details)'}\n\n"
        f"— {settings.APP_NAME}"
    )
    html = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1A0B2E">
  <div style="background:linear-gradient(135deg,#F0115E,#92278E);padding:18px 22px;border-radius:12px 12px 0 0">
    <div style="color:#fff;font-size:16px;font-weight:700">Minutes of Meeting</div>
    <div style="color:rgba(255,255,255,0.85);font-size:12px">{doc.company} · {doc.date} · {doc.purpose}</div>
  </div>
  <div style="border:1px solid #eee;border-top:none;padding:20px;border-radius:0 0 12px 12px;font-size:14px;line-height:1.5">
    {(doc.ai_mom_summary or '(no summary generated yet — see attached document for details)').replace(chr(10), '<br>')}
    <p style="color:#999;font-size:11px;border-top:1px solid #eee;padding-top:10px;margin-top:16px">
      Sent via {settings.APP_NAME}
    </p>
  </div>
</div>"""
    return html, text


class SendMeetingIn(BaseModel):
    to: List[EmailStr]
    cc: List[EmailStr] = []
    subject: Optional[str] = None
    attach_as: Literal["pdf", "docx", "inline"] = "pdf"


@router.post("/{meeting_id}/send")
async def send_meeting(meeting_id: str, body: SendMeetingIn, request: Request,
                        background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Sends the minutes directly to the customer. To/Cc come from the
    request body, not re-derived from the meeting's attendee list server-
    side — the frontend pre-fills them from attendee emails (UIUX spec
    §4.5), but the human reviewing the send modal is the actual authority
    on who receives it, so this endpoint trusts what's sent rather than
    silently overriding it.

    Governance never sends anything to a customer — viewer only."""
    deny_governance(user)
    if not body.to:
        raise HTTPException(400, "At least one recipient (To) is required.")
    m = await _get_meeting_or_404(meeting_id, db, user)
    doc = export_svc.build_minutes_document(m)
    subject = body.subject or f"Minutes of Meeting — {m.company} — {m.date}"

    attachment = None
    if body.attach_as in ("pdf", "docx"):
        render_fn, mimetype, ext = export_svc.EXPORT_RENDERERS[body.attach_as]
        content = render_fn(doc)
        filename = f"MOM_{m.company.replace(' ', '_')}_{m.date}.{ext}"
        attachment = (filename, content, mimetype)

    html_body, text_body = _render_send_body(doc)
    sent = await email_service.send_email(
        to_emails=[str(e) for e in body.to],
        cc_emails=[str(e) for e in body.cc],
        subject=subject, html_body=html_body, text_body=text_body,
        attachment=attachment,
    )

    background_tasks.add_task(
        audit, db, user, "SEND_MOM", "meeting", meeting_id,
        f"{m.company}: minutes sent to {', '.join(str(e) for e in body.to)}"
        + (f" (cc: {', '.join(str(e) for e in body.cc)})" if body.cc else ""),
        request=request
    )
    return {"sent": sent, "to": body.to, "cc": body.cc,
            "message": "Sent." if sent else "SMTP not configured — logged instead of sent (dev mode)."}
