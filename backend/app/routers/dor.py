"""Daily Operations Report (DOR) — Service Delivery Manager's day-to-day
operational log. Lightweight by design (no approval workflow, unlike DSR):
this is a running pulse for the Reports section and dashboards, not what
feeds FGA (FGA uses ManualMetricEntry period aggregates — see scoring.py).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User, DORDaily, role_level
from app.services.deps import get_current_user, require_level

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
