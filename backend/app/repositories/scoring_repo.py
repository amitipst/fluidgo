"""Data-access layer for the config-driven scoring engine."""
from typing import Optional
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ScoringTemplate, ScoringParameter, ScoringResult, RevenueTarget


async def get_active_template(db: AsyncSession, role_key: str) -> Optional[ScoringTemplate]:
    result = await db.execute(
        select(ScoringTemplate).where(ScoringTemplate.role_key == role_key,
                                       ScoringTemplate.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_parameters(db: AsyncSession, template_id: uuid.UUID) -> list[ScoringParameter]:
    result = await db.execute(
        select(ScoringParameter).where(ScoringParameter.template_id == template_id)
        .order_by(ScoringParameter.sort_order)
    )
    return list(result.scalars().all())


async def get_cached_result(db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID,
                             period: str, ttl_hours: int = 6) -> Optional[ScoringResult]:
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
    result = await db.execute(
        select(ScoringResult).where(ScoringResult.user_id == user_id,
                                     ScoringResult.template_id == template_id,
                                     ScoringResult.period == period,
                                     ScoringResult.computed_at > cutoff)
        .order_by(ScoringResult.computed_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def save_result(db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID,
                       period: str, score: float, breakdown: dict) -> ScoringResult:
    row = ScoringResult(user_id=user_id, template_id=template_id, period=period,
                         score=score, breakdown=breakdown)
    db.add(row)
    await db.commit()
    return row


async def get_target(db: AsyncSession, user_id: uuid.UUID, period: str) -> Optional[RevenueTarget]:
    result = await db.execute(
        select(RevenueTarget).where(RevenueTarget.user_id == user_id, RevenueTarget.period == period)
    )
    return result.scalar_one_or_none()
