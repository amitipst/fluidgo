from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User, DSRDaily, SelfScore
from app.services.deps import get_current_user, require_role
from app.services.rigor_service import calculate_rigor_score, rigor_label

router = APIRouter()

class SelfScoreIn(BaseModel):
    market_coverage: Optional[int] = Field(default=None, ge=0, le=5)
    lead_generation: Optional[int] = Field(default=None, ge=0, le=5)
    followup_discipline: Optional[int] = Field(default=None, ge=0, le=5)
    quality_of_conv: Optional[int] = Field(default=None, ge=0, le=5)
    commitment_to_close: Optional[int] = Field(default=None, ge=0, le=5)

class DSRIn(BaseModel):
    date: date
    status: Literal["working", "leave", "holiday", "wfh"] = "working"
    visits: int = 0
    virtual_meetings: int = 0
    calls: int = 0
    new_leads: int = 0
    followups: int = 0
    proposals: int = 0
    notes: Optional[str] = None
    self_scores: Optional[SelfScoreIn] = None

@router.post("")
async def submit_dsr(body: DSRIn, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    # Upsert — one DSR per user per date
    result = await db.execute(
        select(DSRDaily).where(and_(DSRDaily.user_id == user.id,
                                    DSRDaily.date == body.date))
    )
    dsr = result.scalar_one_or_none()
    if dsr:
        for k, v in body.model_dump(exclude={"self_scores"}).items():
            setattr(dsr, k, v)
    else:
        dsr = DSRDaily(user_id=user.id, **body.model_dump(exclude={"self_scores"}))
        db.add(dsr)
    await db.flush()

    if body.self_scores:
        score_res = await db.execute(select(SelfScore).where(SelfScore.dsr_id == dsr.id))
        ss = score_res.scalar_one_or_none()
        if not ss:
            ss = SelfScore(dsr_id=dsr.id)
            db.add(ss)
        for k, v in body.self_scores.model_dump().items():
            if v is not None:
                setattr(ss, k, v)

    await db.commit()
    rigor = calculate_rigor_score(dsr)
    return {"id": str(dsr.id), "rigor_score": rigor, "rigor_label": rigor_label(rigor)}

@router.get("")
async def get_my_dsr(date: date, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    result = await db.execute(
        select(DSRDaily).where(and_(DSRDaily.user_id == user.id, DSRDaily.date == date))
    )
    dsr = result.scalar_one_or_none()
    if not dsr:
        return None
    rigor = calculate_rigor_score(dsr)
    d = {c.name: getattr(dsr, c.name) for c in dsr.__table__.columns}
    d["rigor_score"] = rigor
    d["rigor_label"] = rigor_label(rigor)
    return d

@router.get("/team")
async def get_team_dsr(date: date, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_role("manager", "bu_head", "inside_sales"))):
    result = await db.execute(select(DSRDaily).where(DSRDaily.date == date))
    dsrs = result.scalars().all()
    out = []
    for dsr in dsrs:
        rigor = calculate_rigor_score(dsr)
        d = {c.name: getattr(dsr, c.name) for c in dsr.__table__.columns}
        d["rigor_score"] = rigor
        d["rigor_label"] = rigor_label(rigor)
        out.append(d)
    return out
