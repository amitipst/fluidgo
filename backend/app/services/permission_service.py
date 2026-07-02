"""Data-scope resolver for the org-role hierarchy. Purely additive: existing
require_role() checks in deps.py are untouched and keep gating access as before.
New v2 routers call resolve_visible_user_ids() to filter query results by scope."""
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.repositories import role_repo
from app.services.deps import get_current_user


def require_org_role(*role_keys: str):
    """Mirrors deps.require_role() but checks the new org_role_key instead of the
    legacy `role` column — used for v2-only admin surfaces (scoring templates, org
    role management) that have no equivalent in the original 4-role model."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.org_role_key not in role_keys:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user
    return checker


async def resolve_visible_user_ids(db: AsyncSession, current_user: User) -> Optional[list]:
    """None means 'no restriction — see everyone'. Otherwise a list of user_ids the
    current_user is allowed to see, based on their org_role_key's data_scope."""
    if not current_user.org_role_key:
        return [current_user.id]  # no v2 role mapped yet -> safest default is own-only

    role = await role_repo.get_role(db, current_user.org_role_key)
    if not role:
        return [current_user.id]

    if role.data_scope == "own":
        return [current_user.id]
    if role.data_scope in ("all", "practice"):
        return None
    if role.data_scope in ("bu", "team"):
        # 'team' scope should follow a manager's direct reports, but that reporting-line
        # FK doesn't exist on `users` yet — falls back to BU scope until it's added
        # (tracked as Phase 2 backlog; does not block Phase 1).
        users = await role_repo.list_users_in_bu(db, current_user.bu)
        return [u.id for u in users]
    return [current_user.id]
