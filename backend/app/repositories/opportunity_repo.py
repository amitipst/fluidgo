"""Data-access layer for Opportunities — reads/writes the existing `pipeline` table.
New v2 code (routers/opportunities.py) goes through here; the original pipeline.py
router keeps talking to the ORM directly and is untouched."""
from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PipelineDeal


async def list_opportunities(
    db: AsyncSession,
    user_ids: Optional[list[uuid.UUID]] = None,
    practice: Optional[str] = None,
    oem: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> list[PipelineDeal]:
    query = select(PipelineDeal)
    if user_ids is not None:
        query = query.where(PipelineDeal.user_id.in_(user_ids))
    if practice:
        query = query.where(PipelineDeal.practice == practice)
    if oem:
        query = query.where(PipelineDeal.oem == oem)
    if risk_level:
        query = query.where(PipelineDeal.risk_level == risk_level)
    query = query.order_by(PipelineDeal.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_opportunity(db: AsyncSession, deal_id: str) -> Optional[PipelineDeal]:
    result = await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))
    return result.scalar_one_or_none()


async def list_opportunities_for_health_scan(db: AsyncSession, user_ids: Optional[list[uuid.UUID]] = None) -> list[PipelineDeal]:
    """Open (not closed) deals — the population Deal Health scoring applies to."""
    query = select(PipelineDeal).where(PipelineDeal.stage.notin_(["closed_won", "closed_lost"]))
    if user_ids is not None:
        query = query.where(PipelineDeal.user_id.in_(user_ids))
    result = await db.execute(query)
    return list(result.scalars().all())
