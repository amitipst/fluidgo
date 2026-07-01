from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import date
from typing import Optional
import uuid
from app.database import get_db
from app.models import User, DSRDaily
from app.services.deps import get_current_user, require_role
from app.services.rigor_service import calculate_rigor_score, rigor_label

router = APIRouter()

@router.get("/rep/{user_id}")
async def rep_analytics(user_id: str, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    result = await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == uuid.UUID(user_id))
        .order_by(DSRDaily.date.asc())
    )
    dsrs = result.scalars().all()
    return [
        {**{c.name: getattr(d, c.name) for c in d.__table__.columns},
         "rigor_score": calculate_rigor_score(d),
         "rigor_label": rigor_label(calculate_rigor_score(d))}
        for d in dsrs
    ]

@router.get("/team")
async def team_analytics(db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_role("manager", "bu_head"))):
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()
    out = []
    for u in users:
        dsrs_result = await db.execute(
            select(DSRDaily).where(DSRDaily.user_id == u.id)
        )
        dsrs = dsrs_result.scalars().all()
        working = [d for d in dsrs if d.status == "working"]
        avg_rigor = (sum(calculate_rigor_score(d) for d in working) / len(working)) if working else 0
        out.append({
            "user_id": str(u.id), "name": u.name, "role": u.role,
            "total_days": len(dsrs), "working_days": len(working),
            "total_calls": sum(d.calls for d in dsrs),
            "total_visits": sum(d.visits for d in dsrs),
            "total_followups": sum(d.followups for d in dsrs),
            "total_leads": sum(d.new_leads for d in dsrs),
            "total_proposals": sum(d.proposals for d in dsrs),
            "avg_rigor": round(avg_rigor, 1),
            "rigor_label": rigor_label(int(avg_rigor))
        })
    return sorted(out, key=lambda x: x["avg_rigor"], reverse=True)
