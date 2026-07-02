from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Literal
from app.database import get_db
from app.models import User
from app.services.deps import get_current_user, require_role
from app.services.auth_service import hash_password

router = APIRouter()

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["rep", "inside_sales", "manager", "bu_head"]
    bu: str = "West"

class UserStatusUpdate(BaseModel):
    is_active: bool

def _serialize(u: User) -> dict:
    return {"id": str(u.id), "name": u.name, "email": u.email, "role": u.role,
            "bu": u.bu, "is_active": u.is_active, "created_at": u.created_at}

@router.get("")
async def list_users(db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_role("manager", "bu_head"))):
    result = await db.execute(select(User).order_by(User.is_active.desc(), User.name))
    return [_serialize(u) for u in result.scalars().all()]

@router.post("")
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_role("manager", "bu_head"))):
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "A user with this email already exists")
    new_user = User(name=body.name, email=body.email,
                     password_hash=hash_password(body.password),
                     role=body.role, bu=body.bu, is_active=True)
    db.add(new_user)
    await db.commit()
    return _serialize(new_user)

@router.patch("/{user_id}/status")
async def set_user_status(user_id: str, body: UserStatusUpdate, db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_role("manager", "bu_head"))):
    # Deactivating only flips this flag — every DSR/meeting/lead/pipeline row the
    # person ever created stays untouched (they FK to users.id, which still exists),
    # so historical analytics/AI insights for an exited rep remain fully queryable.
    if str(user.id) == user_id and not body.is_active:
        raise HTTPException(400, "You cannot deactivate your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")
    target.is_active = body.is_active
    await db.commit()
    return _serialize(target)
