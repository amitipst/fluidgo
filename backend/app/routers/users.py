from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User, ROLE_HIERARCHY, role_level
from app.services.deps import get_current_user, require_level
from app.services.auth_service import hash_password
from app.services.permission_service import resolve_visible_user_ids
from app.services.audit_service import audit

router = APIRouter()

# v3 roles — all valid values
V3_ROLES = Literal[
    "rep", "inside_sales", "pre_sales", "manager",
    "bu_head", "business_head", "coo", "hr", "finance", "ceo", "super_admin"
]
BUSINESSES = Literal["fluidpro", "fluidprint", "floxtax", "hooks"]

# India regions — canonical list
INDIA_REGIONS = [
    "India - North",
    "India - South",
    "India - West",
    "India - East",
    "India - Central",
]

class UserCreate(BaseModel):
    name:       str
    email:      EmailStr
    password:   str = Field(min_length=8)
    role:       V3_ROLES = "rep"
    region:     str = "India - West"     # canonical region
    business:   BUSINESSES = "fluidpro"
    manager_id: Optional[str] = None

class UserUpdate(BaseModel):
    name:       Optional[str] = None
    role:       Optional[V3_ROLES] = None
    region:     Optional[str] = None
    business:   Optional[BUSINESSES] = None
    manager_id: Optional[str] = None

class UserStatusUpdate(BaseModel):
    is_active: bool

def _serialize(u: User) -> dict:
    return {
        "id":         str(u.id),
        "name":       u.name,
        "email":      u.email,
        "role":       u.role,
        "role_level": role_level(u.role),
        "region":     getattr(u, "region", None) or u.bu,  # new region field
        "bu":         u.bu,                                  # legacy compat
        "business":   u.business,
        "manager_id": str(u.manager_id) if u.manager_id else None,
        "is_active":  u.is_active,
        "created_at": u.created_at,
    }

def _can_create_role(actor_role: str, target_role: str) -> bool:
    """Enforce: you can only create roles at a lower level than yourself.
    BU Head can create manager and below.
    Manager can create rep/inside_sales/pre_sales only.
    CEO/super_admin can create anything."""
    actor_level  = role_level(actor_role)
    target_level = role_level(target_role)
    return actor_level > target_level

@router.get("")
async def list_users(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20))
):
    """Returns users visible to the current user's scope.
    Manager → their team, BU Head → their BU, CEO → everyone."""
    visible = await resolve_visible_user_ids(db, user)
    query = select(User)
    if visible is not None:
        query = query.where(User.id.in_(visible))
    if not include_inactive:
        query = query.where(User.is_active == True)
    query = query.order_by(User.is_active.desc(), User.name)
    return [_serialize(u) for u in (await db.execute(query)).scalars().all()]

@router.post("")
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_level(20))
):
    # Enforce role hierarchy — can't create someone at your own level or above
    if not _can_create_role(actor.role, body.role):
        raise HTTPException(403,
            f"'{actor.role}' cannot create a user with role '{body.role}'. "
            f"You can only create roles below your own level.")

    # Enforce region isolation — managers can only create in their own region
    user_region = getattr(actor, "region", None) or actor.bu
    if role_level(actor.role) < 50 and role_level(actor.role) < 40:
        if body.region and body.region != user_region:
            raise HTTPException(403,
                f"You can only onboard users to your own region ({user_region})")

    existing = (await db.execute(
        select(User).where(User.email == body.email)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "A user with this email already exists")

    new_user = User(
        name=body.name, email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        bu=body.region.split(" - ")[-1] if " - " in body.region else body.region,  # legacy compat
        region=body.region,
        business=body.business,
        is_active=True,
        manager_id=uuid.UUID(body.manager_id) if body.manager_id else None
    )
    db.add(new_user)
    await db.commit()
    return _serialize(new_user)

@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_level(20))
):
    target = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")

    # Enforce scope — actor must be able to see this user
    visible = await resolve_visible_user_ids(db, actor)
    if visible is not None and target.id not in visible:
        raise HTTPException(403, "You cannot modify this user")

    # Enforce hierarchy against the target's CURRENT role — not just the new role
    # being assigned. Without this, an actor could leave `role` untouched and still
    # edit region/business/manager_id on an account that outranks them, or demote a
    # superior by changing their role to something low enough that _can_create_role
    # would pass. super_admin is exempt (matches require_role's bypass elsewhere);
    # everyone else — including another super_admin — cannot touch an equal-or-higher
    # account. Self-edits are still allowed (e.g. updating your own region).
    if actor.role != "super_admin" and actor.id != target.id:
        if role_level(actor.role) <= role_level(target.role):
            raise HTTPException(403,
                f"Cannot modify a '{target.role}' account — it is at or above your own role level.")

    # Enforce hierarchy if changing role
    if body.role and not _can_create_role(actor.role, body.role):
        raise HTTPException(403, f"Cannot assign role '{body.role}' — insufficient level")

    # If reassigning manager, the new manager must be someone the actor can see
    # and must actually be able to manage (level 20+), so DSR approval chains stay valid.
    if body.manager_id:
        new_mgr = (await db.execute(
            select(User).where(User.id == uuid.UUID(body.manager_id))
        )).scalar_one_or_none()
        if not new_mgr:
            raise HTTPException(404, "New manager not found")
        if role_level(new_mgr.role) < 20:
            raise HTTPException(400, f"'{new_mgr.name}' has role '{new_mgr.role}' and cannot be set as a manager")
        if visible is not None and new_mgr.id not in visible:
            raise HTTPException(403, "You cannot assign a manager outside your scope")

    # Capture before/after for audit trail (region/BU transfer, manager change, role change)
    before = {
        "name": target.name, "role": target.role, "region": getattr(target, "region", None) or target.bu,
        "business": target.business, "manager_id": str(target.manager_id) if target.manager_id else None,
    }

    if body.name:       target.name = body.name
    if body.role:       target.role = body.role
    if body.region:
        target.region = body.region
        target.bu = body.region.split(" - ")[-1] if " - " in body.region else body.region
    if body.business:   target.business = body.business
    if body.manager_id is not None:
        target.manager_id = uuid.UUID(body.manager_id) if body.manager_id else None

    await db.commit()
    await db.refresh(target)

    after = {
        "name": target.name, "role": target.role, "region": getattr(target, "region", None) or target.bu,
        "business": target.business, "manager_id": str(target.manager_id) if target.manager_id else None,
    }
    changed = {k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]}
    if changed:
        summary_bits = []
        if "manager_id" in changed: summary_bits.append("manager reassigned")
        if "region" in changed:     summary_bits.append(f"region/BU transferred to {after['region']}")
        if "role" in changed:      summary_bits.append(f"role changed to {after['role']}")
        background_tasks.add_task(
            audit, db, actor, "UPDATE", "user", str(target.id),
            f"{target.name}: {', '.join(summary_bits) or 'profile updated'}",
            diff=changed, request=request,
        )

    return _serialize(target)

@router.patch("/{user_id}/status")
async def set_user_status(
    user_id: str,
    body: UserStatusUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_level(20))
):
    if str(actor.id) == user_id and not body.is_active:
        raise HTTPException(400, "You cannot deactivate your own account")
    target = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")
    # Enforce hierarchy — can't deactivate someone at same or higher level.
    # No super_admin bypass here on purpose: this is the one action even a
    # super_admin cannot perform on a fellow super_admin — deliberately requires
    # a direct script (same pattern as promote_coo.py) if that's ever truly needed.
    if role_level(actor.role) <= role_level(target.role) and actor.id != target.id:
        raise HTTPException(403, f"Cannot change status of a '{target.role}' account")
    target.is_active = body.is_active
    await db.commit()
    background_tasks.add_task(
        audit, db, actor, "DEACTIVATE" if not body.is_active else "REACTIVATE", "user",
        str(target.id), f"{target.name} ({target.role}) {'deactivated' if not body.is_active else 'reactivated'}",
        request=request,
    )
    return _serialize(target)

@router.get("/roles")
async def list_roles(user: User = Depends(require_level(20))):
    """Returns all roles that the current user is allowed to assign."""
    my_level = role_level(user.role)
    return [
        {"key": k, "label": k.replace("_"," ").title(), "level": v["level"], "scope": v["scope"]}
        for k, v in ROLE_HIERARCHY.items()
        if v["level"] < my_level
    ]

@router.get("/regions")
async def list_regions():
    """Returns canonical India region list for team member creation."""
    return [
        {"key": r, "label": r} for r in INDIA_REGIONS
    ]

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return _serialize(user)
