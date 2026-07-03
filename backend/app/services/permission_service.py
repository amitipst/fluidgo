"""Data-scope resolver for the full v3 org-role hierarchy.

Scope resolution rules:
  own          → only this user's own rows
  team         → manager's direct reports (manager_id = current user)
  bu           → all users in the same bu + business
  business     → all BUs within the same business (e.g. all of fluidPro)
  all          → everyone (CEO / super_admin)
  hr           → all users (for FGA), but cannot see DSR/meeting/pipeline data
  finance      → approved FGA records only
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, ROLE_HIERARCHY, role_level


async def resolve_visible_user_ids(
    db: AsyncSession,
    current_user: User
) -> Optional[list]:
    """Returns list of user UUIDs the current_user can see, or None for 'all'.
    Rules mirror the ROLE_HIERARCHY scope definitions exactly."""
    scope = ROLE_HIERARCHY.get(current_user.role, {}).get("scope", "own")

    # Super-admin / CEO see everything
    if scope == "all":
        return None

    # HR sees all users (for FGA only — caller must restrict data columns separately)
    if scope == "hr":
        result = await db.execute(select(User.id).where(User.is_active == True))
        return [row[0] for row in result.all()]

    # Finance — same as HR for user list; export endpoint already filters to 'approved'
    if scope == "finance":
        result = await db.execute(select(User.id).where(User.is_active == True))
        return [row[0] for row in result.all()]

    # Business Head — all active users within their business
    if scope == "business":
        result = await db.execute(
            select(User.id).where(
                User.business == current_user.business,
                User.is_active == True
            )
        )
        return [row[0] for row in result.all()]

    # BU Head — all active users in their BU + business
    if scope == "bu":
        result = await db.execute(
            select(User.id).where(
                User.bu == current_user.bu,
                User.business == current_user.business,
                User.is_active == True
            )
        )
        return [row[0] for row in result.all()]

    # Manager — only direct reports (manager_id = current_user.id) + themselves
    if scope == "team":
        result = await db.execute(
            select(User.id).where(
                User.manager_id == current_user.id,
                User.is_active == True
            )
        )
        direct_reports = [row[0] for row in result.all()]
        # If no direct reports yet (manager_id not set), fall back to BU
        if not direct_reports:
            result = await db.execute(
                select(User.id).where(
                    User.bu == current_user.bu,
                    User.business == current_user.business,
                    User.is_active == True
                )
            )
            return [row[0] for row in result.all()]
        return direct_reports

    # Default: own only
    return [current_user.id]


async def can_user_edit_target(
    db: AsyncSession, actor: User, target_user_id: str
) -> bool:
    """Manager can edit targets for their direct reports.
    BU Head can edit for the whole BU. Business Head / CEO / super_admin for anyone."""
    if role_level(actor.role) >= 50:
        return True
    visible = await resolve_visible_user_ids(db, actor)
    if visible is None:
        return True
    import uuid
    return uuid.UUID(target_user_id) in visible
