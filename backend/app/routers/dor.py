"""Daily Operations Report (DOR) — Service Delivery Manager's day-to-day
operational log. Lightweight by design compared to DSR: a simple manager
approve/reject exists (see approve_dor below), but deliberately no
edit-lock/window - the SDM can always resubmit. This is a running pulse
for the Reports section and dashboards, not what feeds FGA (FGA uses
ManualMetricEntry period aggregates — see scoring.py).
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User, DORDaily, PipelineDeal, role_level
from app.services.deps import get_current_user, require_level
from app.services.account_service import get_or_create_account
from app.services.audit_service import audit

router = APIRouter()

DOR_ALLOWED_ROLES = {"service_delivery_manager"}


class DORIn(BaseModel):
    date: date
    client_account: Optional[str] = None
    status: Literal["on_track", "at_risk", "critical"] = "on_track"
    tickets_open_start:    int = 0
    tickets_new:           int = 0
    tickets_closed:        int = 0
    tickets_overdue:       int = 0
    escalations_raised:    int = 0
    escalations_resolved:  int = 0
    collection_calls_made: int = 0
    collection_amount:     Optional[float] = None
    client_meetings_held:  int = 0
    resource_deployed:     Optional[int] = None
    resource_available:    Optional[int] = None
    blockers_notes:        Optional[str] = None


def _serialize(d: DORDaily) -> dict:
    return {
        "id": str(d.id), "user_id": str(d.user_id), "date": d.report_date.isoformat(),
        "client_account": d.client_account, "status": d.status,
        "tickets_open_start": d.tickets_open_start, "tickets_new": d.tickets_new,
        "tickets_closed": d.tickets_closed, "tickets_overdue": d.tickets_overdue,
        "escalations_raised": d.escalations_raised, "escalations_resolved": d.escalations_resolved,
        "collection_calls_made": d.collection_calls_made,
        "collection_amount": float(d.collection_amount) if d.collection_amount is not None else None,
        "client_meetings_held": d.client_meetings_held,
        "resource_deployed": d.resource_deployed, "resource_available": d.resource_available,
        "blockers_notes": d.blockers_notes,
        "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        "approval_status": d.approval_status,
        "approved_by": str(d.approved_by) if d.approved_by else None,
        "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "manager_comment": d.manager_comment,
    }


@router.post("")
async def submit_dor(body: DORIn, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """Submit or update today's (or any date's) DOR — upserted by (user, date),
    same pattern as revenue targets: re-submitting the same date corrects it
    in place rather than creating a duplicate row."""
    if user.role not in DOR_ALLOWED_ROLES and role_level(user.role) < 20:
        raise HTTPException(403, "Only Service Delivery Managers (or their managers, editing on their behalf) can submit a DOR")

    existing = (await db.execute(
        select(DORDaily).where(DORDaily.user_id == user.id, DORDaily.report_date == body.date)
    )).scalar_one_or_none()

    fields = body.model_dump(exclude={"date"})
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        existing.submitted_at = datetime.utcnow()
        # Any edit resets approval status - a corrected/rejected entry goes
        # back to "submitted" so it's visible for (re-)review, same reasoning
        # as DSR's submit_dsr (though DOR has no self-edit window to bypass).
        existing.approval_status = "submitted"
        row = existing
    else:
        row = DORDaily(user_id=user.id, report_date=body.date, submitted_at=datetime.utcnow(), **fields)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize(row)


@router.get("/history")
async def dor_history(month: Optional[str] = None, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Own DOR entries for a month (default: current month)."""
    today = date.today()
    ym = month or f"{today.year}-{today.month:02d}"
    yr, mo = int(ym[:4]), int(ym[5:7])
    from calendar import monthrange
    start, end = date(yr, mo, 1), date(yr, mo, monthrange(yr, mo)[1])
    rows = (await db.execute(
        select(DORDaily).where(
            DORDaily.user_id == user.id,
            DORDaily.report_date >= start, DORDaily.report_date <= end,
        ).order_by(DORDaily.report_date.desc())
    )).scalars().all()
    return [_serialize(d) for d in rows]


@router.get("/team")
async def team_dor(month: Optional[str] = None, db: AsyncSession = Depends(get_db),
                   user: User = Depends(require_level(20))):
    """Team's DOR entries for a month — scoped by permission_service, same as
    every other team endpoint (a Business Head sees all SDMs in their business,
    a manager sees their own reports chain, etc.)."""
    from app.services.permission_service import resolve_visible_user_ids
    today = date.today()
    ym = month or f"{today.year}-{today.month:02d}"
    yr, mo = int(ym[:4]), int(ym[5:7])
    from calendar import monthrange
    start, end = date(yr, mo, 1), date(yr, mo, monthrange(yr, mo)[1])

    visible = await resolve_visible_user_ids(db, user)
    q = select(DORDaily).where(DORDaily.report_date >= start, DORDaily.report_date <= end)
    if visible is not None:
        q = q.where(DORDaily.user_id.in_(visible))
    rows = (await db.execute(q.order_by(DORDaily.report_date.desc()))).scalars().all()

    users = {u.id: u for u in (await db.execute(select(User))).scalars().all()}
    out = []
    for d in rows:
        row = _serialize(d)
        u = users.get(d.user_id)
        row["name"] = u.name if u else None
        row["email"] = u.email if u else None
        out.append(row)
    return out


class DORApprovalIn(BaseModel):
    action:  Literal["approve", "reject"]
    comment: Optional[str] = None


@router.post("/{dor_id}/approve")
async def approve_dor(dor_id: str, body: DORApprovalIn, background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_level(20))):
    """Simple manager approve/reject on a DOR entry - no edit-lock/window
    like DSR (see module docstring). Rejecting sets approval_status to
    "rejected" with the manager's comment; the SDM can always resubmit
    (submit_dor resets to "submitted" on any save), which is what brings
    it back for review."""
    from app.services.permission_service import resolve_visible_user_ids

    dor = (await db.execute(select(DORDaily).where(DORDaily.id == uuid.UUID(dor_id)))).scalar_one_or_none()
    if not dor:
        raise HTTPException(404, "DOR entry not found")

    visible = await resolve_visible_user_ids(db, user)
    if visible is not None and dor.user_id not in visible:
        raise HTTPException(403, "You cannot approve DOR entries outside your team")

    if dor.approval_status == "approved" and body.action == "approve":
        raise HTTPException(400, "DOR entry is already approved")

    if body.action == "approve":
        dor.approval_status = "approved"
        dor.approved_by     = user.id
        dor.approved_at     = datetime.utcnow()
        dor.manager_comment = body.comment
        summary = f"DOR approved for {dor.report_date}"
    else:
        dor.approval_status = "rejected"
        dor.approved_by     = None
        dor.approved_at     = None
        dor.manager_comment = body.comment
        summary = f"DOR rejected for {dor.report_date}: {body.comment or 'No reason given'}"

    await db.commit()
    background_tasks.add_task(audit, db, user, f"DOR_{body.action.upper()}", "dor", dor_id, summary)
    return {"dor_id": dor_id, "approval_status": dor.approval_status, "action": body.action}


# ─────────────────────────────────────────────────────────────────────────────
# CSG Phase 1 — farming signal. An SDM (or their manager) notices something in
# a delivery conversation worth Sales following up on (expansion, renewal,
# cross-sell) and flags it here. This creates a REAL PipelineDeal — deal_type
# 'farming', source 'service_delivery' — on the shared Account, visible to
# whoever it's assigned to like any other deal. No AI, no auto-detection;
# that's Phase 5 once there's enough meeting/SIP history to train on. This is
# the human-in-the-loop version of the same idea, shippable now.
#
# Default assignment: an SDM doesn't work Sales pipeline, so a flag they raise
# defaults to THEIR MANAGER (Business Head or their reporting line) for
# triage — not to the SDM themselves, who has no way to action a deal. The
# manager (or Business Head) then reassigns to the right sales rep via
# Pipeline → Reassign. assign_to_user_id lets the flagger pick a specific
# person directly when they already know who should get it.
# ─────────────────────────────────────────────────────────────────────────────

class FlagOpportunityIn(BaseModel):
    notes: str
    potential_value: Optional[float] = None
    assign_to_user_id: Optional[str] = None   # explicit target; defaults to the flagger's manager


@router.post("/{dor_id}/flag-opportunity")
async def flag_opportunity(dor_id: str, body: FlagOpportunityIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_level(20))):
    dor = (await db.execute(select(DORDaily).where(DORDaily.id == uuid.UUID(dor_id)))).scalar_one_or_none()
    if not dor:
        raise HTTPException(404, "DOR entry not found")
    if not dor.client_account:
        raise HTTPException(400, "This DOR entry has no client/account set — add one before flagging an opportunity")

    sdm = (await db.execute(select(User).where(User.id == dor.user_id))).scalar_one_or_none()
    account = await get_or_create_account(db, dor.client_account, business=(sdm.business if sdm else "fluidpro"))
    dor.account_id = account.id

    if body.assign_to_user_id:
        owner_id = uuid.UUID(body.assign_to_user_id)
    elif user.manager_id:
        owner_id = user.manager_id
    else:
        owner_id = user.id   # no manager on record — safe fallback so the deal always has an owner

    deal = PipelineDeal(
        user_id=owner_id, company=account.name, stage="cold",
        todays_update=f"🛠️ New requirement flagged from Service Delivery ({sdm.name if sdm else 'SDM'}, {dor.report_date}): {body.notes}",
        deal_value=body.potential_value, account_id=account.id,
        deal_type="farming", source="service_delivery",
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return {
        "deal_id": str(deal.id), "account_id": str(account.id), "account_name": account.name,
        "assigned_to": str(owner_id), "deal_type": "farming", "source": "service_delivery",
    }
