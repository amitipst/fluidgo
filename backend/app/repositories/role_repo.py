"""Data-access layer for the org-role hierarchy."""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import OrgRole, User


async def get_role(db: AsyncSession, role_key: str) -> Optional[OrgRole]:
    result = await db.execute(select(OrgRole).where(OrgRole.role_key == role_key))
    return result.scalar_one_or_none()


async def list_roles(db: AsyncSession) -> list[OrgRole]:
    result = await db.execute(select(OrgRole))
    return list(result.scalars().all())


async def list_users_in_bu(db: AsyncSession, bu: str) -> list[User]:
    result = await db.execute(select(User).where(User.bu == bu, User.is_active == True))
    return list(result.scalars().all())


async def list_users_managed_by(db: AsyncSession, manager_id) -> list[User]:
    """Placeholder for a real reporting-line FK (not modeled yet) — for now, 'team'
    scope falls back to same-BU active users, refined once a manager_id column exists
    on users (tracked as v2 Phase 2 backlog, not needed for Phase 1 to function)."""
    return []
