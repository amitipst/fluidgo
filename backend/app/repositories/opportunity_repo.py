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
    include_archived: bool = False,
    include_seed: bool = False,
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
    # Excluded by default for every scope, including user_ids=None
    # (ceo/coo/super_admin) — that's precisely the case that had NO owner
    # filter at all, so archived/dummy deals from deactivated accounts used
    # to show up unfiltered right alongside real data.
    if not include_archived:
        query = query.where(PipelineDeal.archived == False)
    # Seeded deals (seed_v3.py, see migration 0029) excluded by default —
    # same class of leakage fixed for the Meetings list (migration 0027)
    # and pipeline.py's list_deals(). This table is shared with that
    # endpoint, so the two are kept behaviorally consistent: same
    # include_seed toggle, same caller-decides-who-can-set-it-true contract
    # (the router gates it to business_head+, matching list_meetings()).
    if not include_seed:
        query = query.where(PipelineDeal.is_seed == False)
    query = query.order_by(PipelineDeal.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_opportunity(db: AsyncSession, deal_id: str) -> Optional[PipelineDeal]:
    result = await db.execute(select(PipelineDeal).where(PipelineDeal.id == deal_id))
    return result.scalar_one_or_none()


async def list_opportunities_for_health_scan(db: AsyncSession, user_ids: Optional[list[uuid.UUID]] = None) -> list[PipelineDeal]:
    """Open (not closed) deals — the population Deal Health scoring applies to.
    Excludes archived and seeded deals (mirrors list_opportunities() above) —
    otherwise archived/dummy deals get AI-scored and can surface in deal
    health lists and coaching prompts."""
    query = select(PipelineDeal).where(
        PipelineDeal.stage.notin_(["closed_won", "closed_lost"]),
        PipelineDeal.archived == False, PipelineDeal.is_seed == False,
    )
    if user_ids is not None:
        query = query.where(PipelineDeal.user_id.in_(user_ids))
    result = await db.execute(query)
    return list(result.scalars().all())
