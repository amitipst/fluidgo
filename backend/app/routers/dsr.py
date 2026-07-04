from fastapi import APIRouter, Depends, Request, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import date
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User, DSRDaily, SelfScore
from app.services.deps import get_current_user, require_level
from app.services.rigor_service import calculate_rigor_score, rigor_label
from app.services.audit_service import audit

router = APIRouter()

PRESALES_ROLES = {"pre_sales", "presales"}

class SelfScoreIn(BaseModel):
    # Sales dimensions
    market_coverage:       Optional[int] = Field(default=None, ge=0, le=5)
    lead_generation:       Optional[int] = Field(default=None, ge=0, le=5)
    followup_discipline:   Optional[int] = Field(default=None, ge=0, le=5)
    quality_of_conv:       Optional[int] = Field(default=None, ge=0, le=5)
    commitment_to_close:   Optional[int] = Field(default=None, ge=0, le=5)
    # Pre-Sales dimensions
    solution_support:      Optional[int] = Field(default=None, ge=0, le=5)
    technical_conversion:  Optional[int] = Field(default=None, ge=0, le=5)
    knowledge_excellence:  Optional[int] = Field(default=None, ge=0, le=5)
    operational_excellence:Optional[int] = Field(default=None, ge=0, le=5)

class DSRIn(BaseModel):
    date: date
    status: Literal["working","leave","holiday","wfh"] = "working"
    # Sales fields
    visits:           int   = 0
    virtual_meetings: int   = 0
    calls:            int   = 0
    new_leads:        int   = 0
    followups:        int   = 0
    proposals:        int   = 0
    proposal_value:   Optional[float] = None
    travel_day:       bool  = False
    # Pre-Sales fields
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

def _serialize_dsr(dsr: DSRDaily, rigor: int) -> dict:
    d = {c.name: getattr(dsr, c.name) for c in dsr.__table__.columns}
    d["rigor_score"] = rigor
    d["rigor_label"] = rigor_label(rigor)
    # Ensure UUIDs are strings
    d["id"] = str(d["id"])
    d["user_id"] = str(d["user_id"])
    return d

@router.post("")
async def submit_dsr(
    body: DSRIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Upsert DSR — one row per user per date."""
    dsr_type = "presales" if user.role in PRESALES_ROLES else "sales"
    is_update = False

    result = await db.execute(
        select(DSRDaily).where(and_(DSRDaily.user_id == user.id,
                                    DSRDaily.date == body.date))
    )
    dsr = result.scalar_one_or_none()
    payload = body.model_dump(exclude={"self_scores"})
    payload["dsr_type"] = dsr_type

    if dsr:
        is_update = True
        for k, v in payload.items():
            setattr(dsr, k, v)
    else:
        dsr = DSRDaily(user_id=user.id, **payload)
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

    # Audit log — fire and forget
    action = "UPDATE" if is_update else "CREATE"
    background_tasks.add_task(
        audit, db, user, action, "dsr", str(dsr.id),
        f"DSR {action.lower()}d for {body.date} — rigor={rigor}",
        request=request
    )

    return {"id": str(dsr.id), "rigor_score": rigor,
            "rigor_label": rigor_label(rigor), "dsr_type": dsr_type}

@router.get("")
async def get_my_dsr(date: date, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    result = await db.execute(
        select(DSRDaily).where(and_(DSRDaily.user_id == user.id, DSRDaily.date == date))
    )
    dsr = result.scalar_one_or_none()
    if not dsr:
        return None
    return _serialize_dsr(dsr, calculate_rigor_score(dsr))

@router.get("/team")
async def get_team_dsr(date: date, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_level(20))):
    """Returns all DSR rows for today for the current user's visible team."""
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, user)
    query = select(DSRDaily).where(DSRDaily.date == date)
    if visible is not None:
        query = query.where(DSRDaily.user_id.in_(visible))
    result = await db.execute(query)
    return [_serialize_dsr(d, calculate_rigor_score(d)) for d in result.scalars().all()]
