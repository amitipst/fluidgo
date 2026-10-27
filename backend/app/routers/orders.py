"""Orders register (v1.6.1) — closed (won) orders for Finance and leaders.

Read-only. Answers: which orders are booked, on what evidence (PO / email / LOI),
when, for how much, and has Finance invoiced them in the ERP yet?
Visibility: `finance` sees all orders; manager-and-above see their normal scope
(resolve_visible_user_ids). Governance is blocked (no money figures).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, PipelineDeal, role_level
from app.services import pipeline_sheet_service as pss
from app.services.booking_date import won_date_col, won_date_of
from app.services.deps import get_current_user, deny_governance
from app.services.permission_service import resolve_visible_user_ids

router = APIRouter()


def can_view_orders(user: User) -> bool:
    return user.role == "finance" or role_level(user.role) >= 20


@router.get("")
async def list_orders(
    status: Optional[str] = None,       # all | invoiced | pending
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deny_governance(user)
    if not can_view_orders(user):
        raise HTTPException(403, "Orders register is for Finance and managers")
    if status not in (None, "all", "invoiced", "pending"):
        raise HTTPException(422, "status must be all, invoiced or pending")
    visible = await resolve_visible_user_ids(db, user)
    q = select(PipelineDeal).where(
        PipelineDeal.stage == "closed_won",
        PipelineDeal.archived == False,  # noqa: E712
        PipelineDeal.is_seed == False,   # noqa: E712
        PipelineDeal.user_id.in_(visible),
    )
    if date_from:
        q = q.where(won_date_col() >= date_from)
    if date_to:
        q = q.where(won_date_col() <= date_to)
    deals = (await db.execute(q)).scalars().all()
    owners = {u.id: u.name for u in (await db.execute(
        select(User).where(User.id.in_({d.user_id for d in deals})))).scalars().all()} if deals else {}

    rows = []
    for d in deals:
        a = pss.amounts(d.recurring_revenue, d.one_time_revenue, d.deal_value)
        invoiced = d.invoiced_at is not None
        if status == "invoiced" and not invoiced:
            continue
        if status == "pending" and invoiced:
            continue
        wd = won_date_of(d)
        rows.append({
            "id": str(d.id), "company": d.company, "title": d.title,
            "owner": owners.get(d.user_id), "won_date": wd.isoformat() if wd else None,
            "won_basis": d.won_basis, "won_ref": d.won_ref,
            "arr": a["arr"], "one_time": a["one_time"], "total": a["total"],
            "invoiced": invoiced,
            "invoiced_at": d.invoiced_at.isoformat() if d.invoiced_at else None,
            "invoice_ref": d.invoice_ref,
            "evidence_missing": not (d.won_basis and d.won_ref),
        })
    rows.sort(key=lambda r: r["won_date"] or "", reverse=True)
    pend = [r for r in rows if not r["invoiced"]]
    return {
        "orders": rows,
        "summary": {
            "count": len(rows), "total": sum(r["total"] for r in rows),
            "pending_count": len(pend), "pending_total": sum(r["total"] for r in pend),
            "missing_evidence": sum(1 for r in rows if r["evidence_missing"]),
        },
    }
