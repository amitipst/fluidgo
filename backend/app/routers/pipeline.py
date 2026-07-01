from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional, Literal
from app.database import get_db
from app.models import PipelineDeal, User
from app.services.deps import get_current_user

router = APIRouter()

class DealIn(BaseModel):
    company: str
    stage: Literal["cold", "warm", "hot", "closed_won", "closed_lost"] = "cold"
    todays_update: Optional[str] = None
    roadblock: bool = False
    next_step: Optional[str] = None
    closure_eta: Optional[date] = None
    deal_value: Optional[float] = None

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
async def update_deal(deal_id: str, body: DealIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    result = await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        from fastapi import HTTPException
        raise HTTPException(404, "Deal not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(deal, k, v)
    await db.commit()
    return {"id": deal_id, "updated": True}
