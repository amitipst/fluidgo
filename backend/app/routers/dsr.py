from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Literal, List
import uuid
from app.database import get_db
from app.models import User, DSRDaily, SelfScore
from app.services.deps import get_current_user, require_level
from app.services.rigor_service import calculate_rigor_score, rigor_label
from app.services.audit_service import audit

router = APIRouter()

# Self-edit window — see design note on DSRDaily.edit_granted_until.
SELF_EDIT_WINDOW = timedelta(hours=24)
GRANTED_EDIT_WINDOW = timedelta(hours=24)  # duration of a manager-granted exception

# Roles permitted to submit a DSR (field + direct management only)
DSR_ALLOWED_ROLES = {
    "rep", "inside_sales", "pre_sales", "manager"
}
PRESALES_ROLES = {"pre_sales", "presales"}

class SelfScoreIn(BaseModel):
    market_coverage:       Optional[int] = Field(default=None, ge=0, le=5)
    lead_generation:       Optional[int] = Field(default=None, ge=0, le=5)
    followup_discipline:   Optional[int] = Field(default=None, ge=0, le=5)
    quality_of_conv:       Optional[int] = Field(default=None, ge=0, le=5)
    commitment_to_close:   Optional[int] = Field(default=None, ge=0, le=5)
    solution_support:      Optional[int] = Field(default=None, ge=0, le=5)
    technical_conversion:  Optional[int] = Field(default=None, ge=0, le=5)
    knowledge_excellence:  Optional[int] = Field(default=None, ge=0, le=5)
    operational_excellence:Optional[int] = Field(default=None, ge=0, le=5)

class DSRIn(BaseModel):
    date: date
    status: Literal["working","leave","holiday","wfh"] = "working"
    visits:           int   = 0
    virtual_meetings: int   = 0
    calls:            int   = 0
    new_leads:        int   = 0
    followups:        int   = 0
    proposals:        int   = 0
    proposal_value:   Optional[float] = None
    travel_day:       bool  = False
    demos_conducted:      int = 0
    pocs_conducted:       int = 0
    proposals_supported:  int = 0
    tech_discussions:     int = 0
    workshops_conducted:  int = 0
    trainings_delivered:  int = 0
    trainings_attended:   int = 0
    docs_created:         int = 0
    linked_opportunity_id: Optional[str] = None
    notes:            Optional[str] = None
    self_scores:      Optional[SelfScoreIn] = None

class ApprovalIn(BaseModel):
    action:  Literal["approve", "reject"]
    comment: Optional[str] = None

class EditRequestIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)

class GrantEditIn(BaseModel):
    comment: Optional[str] = None

def _aware(dt):
    """Normalize a datetime to UTC-aware so it can be safely compared.
    Postgres timestamptz columns come back tz-aware via asyncpg, but some
    older rows / code paths produce naive datetimes — comparing the two
    raises TypeError, which is what was 500-ing /dsr/history."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

def _edit_lock_state(dsr: DSRDaily) -> dict:
    """Returns why (if at all) a DSR is locked from self-editing right now."""
    now = datetime.now(timezone.utc)
    granted_until = _aware(dsr.edit_granted_until)
    if granted_until and now < granted_until:
        return {"locked": False, "reason": None}
    if dsr.approval_status == "approved":
        return {"locked": True, "reason": "approved",
                "message": "Approved by your manager and cannot be edited. "
                           "Use 'Request Edit' if a correction is genuinely needed."}
    window_ends = _aware(dsr.submitted_at) + SELF_EDIT_WINDOW
    if now < window_ends:
        return {"locked": False, "reason": None, "self_edit_ends_at": window_ends.isoformat()}
    return {"locked": True, "reason": "window_closed",
            "message": "The 24-hour self-edit window has closed. "
                       "Use 'Request Edit' to ask your manager for an exception."}

def _serialize_dsr(dsr: DSRDaily, rigor: int, self_score=None) -> dict:
    d = {c.name: getattr(dsr, c.name) for c in dsr.__table__.columns}
    d["rigor_score"]     = rigor
    d["rigor_label"]     = rigor_label(rigor)
    d["id"]              = str(d["id"])
    d["user_id"]         = str(d["user_id"])
    d["approved_by"]     = str(d["approved_by"]) if d.get("approved_by") else None
    lock = _edit_lock_state(dsr)
    d["is_locked"]       = lock["locked"]
    d["lock_reason"]     = lock.get("reason")
    d["lock_message"]    = lock.get("message")
    d["self_edit_ends_at"] = lock.get("self_edit_ends_at")
    if self_score:
        d["self_scores"] = {
            c.name: getattr(self_score, c.name)
            for c in self_score.__table__.columns
            if c.name not in ("id", "dsr_id")
        }
    return d

# ── Submit / Update DSR ───────────────────────────────────────────────────────
@router.post("")
async def submit_dsr(
    body: DSRIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Upsert DSR — one row per user per date.
    Only field roles (rep, inside_sales, pre_sales, manager) can submit DSR.
    Business heads, CEOs, HR, Finance do not submit DSRs.
    LOCKED once manager approves — rep cannot edit after that."""

    # Role guard — business_head and above do not submit DSRs
    if user.role not in DSR_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user.role}' does not submit DSRs. Only field roles (rep, inside_sales, pre_sales, manager) can submit."
        )

    dsr_type = "presales" if user.role in PRESALES_ROLES else "sales"

    result = await db.execute(
        select(DSRDaily).where(and_(DSRDaily.user_id == user.id,
                                    DSRDaily.date == body.date))
    )
    dsr = result.scalar_one_or_none()

    # Block editing if approved, or if the 24h self-edit window has closed
    # (unless a manager has explicitly granted a temporary exception).
    if dsr:
        lock = _edit_lock_state(dsr)
        if lock["locked"]:
            raise HTTPException(status_code=400, detail=lock["message"])

    is_update = bool(dsr)
    payload   = body.model_dump(exclude={"self_scores"})
    payload["dsr_type"]        = dsr_type
    payload["approval_status"] = "submitted"   # reset to submitted on any edit

    if dsr:
        for k, v in payload.items():
            setattr(dsr, k, v)
    else:
        dsr = DSRDaily(user_id=user.id, **payload)
        db.add(dsr)
    await db.flush()

    if body.self_scores:
        ss_res = await db.execute(select(SelfScore).where(SelfScore.dsr_id == dsr.id))
        ss = ss_res.scalar_one_or_none()
        if not ss:
            ss = SelfScore(dsr_id=dsr.id)
            db.add(ss)
        for k, v in body.self_scores.model_dump().items():
            if v is not None:
                setattr(ss, k, v)

    await db.commit()
    rigor  = calculate_rigor_score(dsr)
    action = "UPDATE" if is_update else "CREATE"
    background_tasks.add_task(
        audit, db, user, action, "dsr", str(dsr.id),
        f"DSR {action.lower()}d for {body.date} — rigor={rigor}, status=submitted",
        request=request
    )

    return {
        "id":              str(dsr.id),
        "rigor_score":     rigor,
        "rigor_label":     rigor_label(rigor),
        "dsr_type":        dsr_type,
        "approval_status": "submitted",
        "is_update":       is_update,
        "message":         f"DSR {'updated' if is_update else 'submitted'} successfully for {body.date}"
    }

# ── Get single DSR for a date ─────────────────────────────────────────────────
@router.get("")
async def get_my_dsr(
    date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(DSRDaily).where(and_(DSRDaily.user_id == user.id, DSRDaily.date == date))
    )
    dsr = result.scalar_one_or_none()
    if not dsr:
        return None
    ss = (await db.execute(select(SelfScore).where(SelfScore.dsr_id == dsr.id))).scalar_one_or_none()
    return _serialize_dsr(dsr, calculate_rigor_score(dsr), ss)

# ── DSR History — rep sees all their own DSRs ─────────────────────────────────
@router.get("/history")
async def get_my_history(
    month: Optional[str] = None,   # "2026-07" format
    limit: int = 60,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Returns all DSR rows for the current user, newest first.
    Optional month filter: ?month=2026-07"""
    q = select(DSRDaily).where(DSRDaily.user_id == user.id)
    if month:
        try:
            yr, mo = int(month[:4]), int(month[5:7])
            from calendar import monthrange
            start = date(yr, mo, 1)
            end   = date(yr, mo, monthrange(yr, mo)[1])
            q = q.where(DSRDaily.date >= start, DSRDaily.date <= end)
        except Exception:
            pass
    q = q.order_by(desc(DSRDaily.date)).limit(limit)
    dsrs = (await db.execute(q)).scalars().all()

    results = []
    for dsr in dsrs:
        rigor = calculate_rigor_score(dsr)
        ss = (await db.execute(
            select(SelfScore).where(SelfScore.dsr_id == dsr.id)
        )).scalar_one_or_none()
        results.append(_serialize_dsr(dsr, rigor, ss))
    return results

# ── Team DSR (manager view) ───────────────────────────────────────────────────
@router.get("/team")
async def get_team_dsr(
    date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20))
):
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    q = select(DSRDaily).where(DSRDaily.date == date)
    if visible is not None:
        q = q.where(DSRDaily.user_id.in_(visible))
    dsrs = (await db.execute(q)).scalars().all()
    return [_serialize_dsr(d, calculate_rigor_score(d)) for d in dsrs]

# ── Team DSR History (manager view — for approval) ────────────────────────────
@router.get("/team/pending")
async def get_pending_approvals(
    month: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20))
):
    """Returns all submitted (unapproved) DSRs for the manager's team."""
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    q = select(DSRDaily).where(DSRDaily.approval_status == "submitted")
    if visible is not None:
        q = q.where(DSRDaily.user_id.in_(visible))
    if month:
        try:
            yr, mo = int(month[:4]), int(month[5:7])
            from calendar import monthrange
            q = q.where(DSRDaily.date >= date(yr, mo, 1),
                        DSRDaily.date <= date(yr, mo, monthrange(yr, mo)[1]))
        except Exception:
            pass
    q = q.order_by(desc(DSRDaily.date))
    dsrs = (await db.execute(q)).scalars().all()

    results = []
    for dsr in dsrs:
        rigor   = calculate_rigor_score(dsr)
        rep     = (await db.execute(select(User).where(User.id == dsr.user_id))).scalar_one_or_none()
        row     = _serialize_dsr(dsr, rigor)
        row["rep_name"]  = rep.name  if rep else "Unknown"
        row["rep_email"] = rep.email if rep else ""
        results.append(row)
    return results

# ── Approve / Reject DSR ──────────────────────────────────────────────────────
@router.post("/{dsr_id}/approve")
async def approve_dsr(
    dsr_id: str,
    body: ApprovalIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20))
):
    """Manager approves or rejects a submitted DSR.
    - approved → rep cannot edit
    - rejected → rep can re-edit and resubmit
    """
    from app.services.permission_service import resolve_visible_user_ids

    dsr = (await db.execute(
        select(DSRDaily).where(DSRDaily.id == uuid.UUID(dsr_id))
    )).scalar_one_or_none()

    if not dsr:
        raise HTTPException(404, "DSR not found")

    # Verify manager has scope over this rep
    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and dsr.user_id not in visible:
        raise HTTPException(403, "You cannot approve DSRs outside your team")

    if dsr.approval_status == "approved" and body.action == "approve":
        raise HTTPException(400, "DSR is already approved")

    if body.action == "approve":
        dsr.approval_status = "approved"
        dsr.approved_by     = user.id
        dsr.approved_at     = datetime.now(timezone.utc)
        dsr.manager_comment = body.comment
        summary = f"DSR approved for {dsr.date}"
    else:  # reject
        dsr.approval_status = "submitted"   # back to editable
        dsr.approved_by     = None
        dsr.approved_at     = None
        dsr.manager_comment = body.comment
        summary = f"DSR rejected for {dsr.date}: {body.comment or 'No reason given'}"

    await db.commit()
    background_tasks.add_task(
        audit, db, user, f"DSR_{body.action.upper()}", "dsr",
        dsr_id, summary, request=request
    )
    return {
        "dsr_id":          dsr_id,
        "approval_status": dsr.approval_status,
        "action":          body.action,
        "comment":         body.comment,
        "message":         f"DSR {body.action}d successfully"
    }

# ── Request a post-window edit exception ──────────────────────────────────────
@router.post("/{dsr_id}/request-edit")
async def request_edit(
    dsr_id: str,
    body: EditRequestIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Rep asks for a locked (approved or window-closed) DSR to be reopened.
    Does NOT unlock anything by itself — just logs the request for the
    manager to see and act on via /grant-edit."""
    dsr = (await db.execute(
        select(DSRDaily).where(DSRDaily.id == uuid.UUID(dsr_id))
    )).scalar_one_or_none()
    if not dsr:
        raise HTTPException(404, "DSR not found")
    if dsr.user_id != user.id:
        raise HTTPException(403, "You can only request edits on your own DSRs")
    if not _edit_lock_state(dsr)["locked"]:
        raise HTTPException(400, "This DSR is still editable — no request needed")

    dsr.edit_request_reason = body.reason
    dsr.edit_requested_at   = datetime.now(timezone.utc)
    await db.commit()
    background_tasks.add_task(
        audit, db, user, "EDIT_REQUESTED", "dsr", dsr_id,
        f"Edit requested for {dsr.date}: {body.reason}", request=request
    )
    return {"message": "Edit request sent to your manager.", "reason": body.reason}

# ── Manager sees pending edit requests for their team ─────────────────────────
@router.get("/team/edit-requests")
async def get_edit_requests(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20))
):
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    q = select(DSRDaily).where(DSRDaily.edit_requested_at.isnot(None))
    if visible is not None:
        q = q.where(DSRDaily.user_id.in_(visible))
    q = q.order_by(desc(DSRDaily.edit_requested_at))
    dsrs = (await db.execute(q)).scalars().all()

    results = []
    for dsr in dsrs:
        # Already-granted-and-still-open requests don't need re-surfacing
        if dsr.edit_granted_until and datetime.now(timezone.utc) < _aware(dsr.edit_granted_until):
            continue
        rep = (await db.execute(select(User).where(User.id == dsr.user_id))).scalar_one_or_none()
        results.append({
            "dsr_id": str(dsr.id), "date": dsr.date.isoformat(),
            "rep_name": rep.name if rep else "Unknown",
            "rep_email": rep.email if rep else "",
            "reason": dsr.edit_request_reason,
            "requested_at": dsr.edit_requested_at.isoformat(),
        })
    return results

# ── Manager grants a temporary reopen ──────────────────────────────────────────
@router.post("/{dsr_id}/grant-edit")
async def grant_edit(
    dsr_id: str,
    body: GrantEditIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20))
):
    """Manager explicitly reopens a locked DSR for 24h. Every grant is
    audited with who/when/why — nothing changes on a past DSR silently."""
    from app.services.permission_service import resolve_visible_user_ids
    dsr = (await db.execute(
        select(DSRDaily).where(DSRDaily.id == uuid.UUID(dsr_id))
    )).scalar_one_or_none()
    if not dsr:
        raise HTTPException(404, "DSR not found")
    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and dsr.user_id not in visible:
        raise HTTPException(403, "You cannot grant edits outside your team")

    dsr.edit_granted_until  = datetime.now(timezone.utc) + GRANTED_EDIT_WINDOW
    dsr.edit_request_reason = None
    dsr.edit_requested_at   = None
    await db.commit()
    background_tasks.add_task(
        audit, db, user, "EDIT_GRANTED", "dsr", dsr_id,
        f"Edit reopened for {dsr.date} until {dsr.edit_granted_until.isoformat()}"
        f"{': ' + body.comment if body.comment else ''}", request=request
    )
    return {"message": "Edit window reopened for 24 hours.",
            "edit_granted_until": dsr.edit_granted_until.isoformat()}
