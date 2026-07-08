from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
from typing import Optional, Literal
from app.database import get_db
from app.models import PipelineDeal, User
from app.services.deps import get_current_user
from app.services.audit_service import audit

router = APIRouter()

class DealIn(BaseModel):
    company: str
    stage: Literal["cold", "warm", "hot", "closed_won", "closed_lost"] = "cold"
    todays_update: Optional[str] = None
    roadblock: bool = False
    next_step: Optional[str] = None
    closure_eta: Optional[date] = None
    deal_value: Optional[float] = None
    # ── v2 Opportunity fields — all optional, existing callers unaffected ──
    bu: Optional[str] = None
    presales_owner_id: Optional[str] = None
    primary_contact: Optional[str] = None
    oem: Optional[str] = None
    solution_area: Optional[Literal["Managed Services", "Cloud", "Licensing", "Security", "Professional Services"]] = None
    practice: Optional[str] = None
    recurring_revenue: Optional[float] = None
    one_time_revenue: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    competition: Optional[str] = None
    risk_level: Optional[Literal["low", "medium", "high", "critical"]] = None
    decision_maker: Optional[str] = None
    budget_status: Optional[Literal["confirmed", "unconfirmed", "unknown"]] = None
    timeline_status: Optional[Literal["on_track", "delayed", "unknown"]] = None
    proposal_version: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None

@router.post("")
async def create_deal(body: DealIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    deal = PipelineDeal(user_id=user.id, **body.model_dump())
    db.add(deal)
    await db.commit()
    return {"id": str(deal.id), **body.model_dump()}

@router.get("")
async def list_deals(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(PipelineDeal).where(PipelineDeal.user_id == user.id).order_by(PipelineDeal.updated_at.desc())
    )
    return [{c.name: getattr(d, c.name) for c in d.__table__.columns} for d in result.scalars().all()]

@router.patch("/{deal_id}")
async def update_deal(deal_id: str, body: DealIn, request: Request,
                      background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    result = await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")

    updates = body.model_dump(exclude_none=True)
    # Capture value/stage changes specifically — these feed revenue forecasting,
    # so a change to them is worth an explicit audit entry.
    old_value = float(deal.deal_value) if deal.deal_value is not None else None
    old_stage = deal.stage

    for k, v in updates.items():
        setattr(deal, k, v)
    # Any edit counts as activity — keeps "stale deal" logic honest.
    deal.last_activity_at = datetime.utcnow()
    await db.commit()

    new_value = float(deal.deal_value) if deal.deal_value is not None else None
    changes = []
    if "deal_value" in updates and old_value != new_value:
        changes.append(f"value {old_value or 0:,.0f} → {new_value or 0:,.0f}")
    if "stage" in updates and old_stage != deal.stage:
        changes.append(f"stage {old_stage} → {deal.stage}")
    if changes:
        background_tasks.add_task(
            audit, db, user, "UPDATE", "pipeline", deal_id,
            f"{deal.company}: {', '.join(changes)}", request=request,
        )
    return {"id": deal_id, "updated": True}
