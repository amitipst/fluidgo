"""
RBAC: Lean and clean role hierarchy for fluidGo.

Simplified from 10 roles to a clear 6-tier system:
  Level 99: super_admin   — full system access, health dashboard, audit logs
  Level 50: ceo           — all businesses, all regions
  Level 40: business_head — all regions within one business (≡ practice_head)
  Level 30: bu_head       — legacy alias for business_head (same access)
  Level 20: manager       — own team via manager_id
  Level 25: hr            — all users for FGA, no sales data
  Level 25: finance       — approved FGA export only
  Level 10: rep           — own data only
  Level 10: inside_sales  — own data only
  Level 10: pre_sales     — own data only

business_head == practice_head (same level 40, same scope)
bu_head is kept as alias → maps to level 30 for backward compat
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, role_level
from app.services.auth_service import decode_token

# auto_error=False so a MISSING Authorization header reaches our own handler
# below (returning a clean 401 the frontend refresh-interceptor recognises)
# instead of HTTPBearer raising its own 403 "Not authenticated" — which the
# interceptor treats as a permissions error and does NOT refresh/retry on.
# That 403-vs-401 mismatch was the "not authenticated" pipeline save error:
# an expired access token → no refresh → raw error surfaced to the user.
bearer = HTTPBearer(auto_error=False)

# Roles that can access management/admin features
MANAGER_ROLES  = {"manager", "bu_head", "business_head", "practice_head", "ceo", "super_admin"}
FIELD_ROLES    = {"rep", "inside_sales", "pre_sales"}
ALL_ROLES      = MANAGER_ROLES | FIELD_ROLES | {"hr", "finance"}

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db)
) -> User:
    # With auto_error=False, a missing header arrives as None — return our own
    # 401 (not HTTPBearer's 403) so the frontend refreshes the token and retries.
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in again",
            headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        payload = decode_token(creds.credentials)
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid — please log in again",
            headers={"WWW-Authenticate": "Bearer"}
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")
    return user


def require_role(*roles: str):
    """Exact role match. Includes super_admin bypass always."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role == "super_admin":
            return user  # super_admin bypasses all role checks
        # Normalize: practice_head == business_head, bu_head >= 30
        effective = user.role
        if user.role == "practice_head":
            effective = "business_head"
        if effective not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' cannot access this resource. Required: {roles}"
            )
        return user
    return checker


def require_level(min_level: int):
    """Level-based guard — any role at or above min_level passes.
    Always allows super_admin (level 99)."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if role_level(user.role) < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient access level (required: {min_level}, your level: {role_level(user.role)})"
            )
        return user
    return checker


def require_any_manager(user: User = Depends(get_current_user)) -> User:
    """Passes for manager and above, plus hr and finance."""
    if role_level(user.role) < 20 and user.role not in ("hr", "finance"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Management role required")
    return user
