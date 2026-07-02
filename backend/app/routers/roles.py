from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Literal
from app.database import get_db
from app.models import User, OrgRole
from app.services.permission_service import require_org_role
from app.repositories import role_repo

router = APIRouter()

ADMIN_ROLES = ("admin", "super_admin")


class RoleIn(BaseModel):
    role_key: str
    display_name: str
    parent_role_key: Optional[str] = None
    data_scope: Literal["own", "team", "bu", "practice", "all"]


class UserRoleAssign(BaseModel):
    org_role_key: str


@router.get("")
async def list_roles(db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_org_role(*ADMIN_ROLES))):
    roles = await role_repo.list_roles(db)
    return [{"role_key": r.role_key, "display_name": r.display_name,
             "parent_role_key": r.parent_role_key, "data_scope": r.data_scope} for r in roles]


@router.post("")
async def upsert_role(body: RoleIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_org_role(*ADMIN_ROLES))):
    existing = await role_repo.get_role(db, body.role_key)
    if existing:
        existing.display_name = body.display_name
        existing.parent_role_key = body.parent_role_key
        existing.data_scope = body.data_scope
    else:
        db.add(OrgRole(**body.model_dump()))
    await db.commit()
    return body


@router.patch("/assign/{user_id}")
async def assign_org_role(user_id: str, body: UserRoleAssign, db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_org_role(*ADMIN_ROLES))):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")
    if not await role_repo.get_role(db, body.org_role_key):
        raise HTTPException(400, f"Unknown org role '{body.org_role_key}'")
    target.org_role_key = body.org_role_key
    await db.commit()
    return {"user_id": user_id, "org_role_key": body.org_role_key}
