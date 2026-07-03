from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, role_level
from app.services.auth_service import decode_token

bearer = HTTPBearer()

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = decode_token(creds.credentials)
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")
    return user

def require_role(*roles: str):
    """Legacy guard — exact role match. Still used throughout."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Role '{user.role}' cannot access this resource")
        return user
    return checker

def require_level(min_level: int):
    """Level-based guard — any role at or above min_level passes.
    Preferred for new endpoints — more future-proof than exact role matching."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if role_level(user.role) < min_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Insufficient role level (need {min_level}, have {role_level(user.role)})")
        return user
    return checker

def require_scope(*scopes: str):
    """Scope-based guard — passes if user's role scope is in allowed scopes."""
    from app.models import ROLE_HIERARCHY
    async def checker(user: User = Depends(get_current_user)) -> User:
        user_scope = ROLE_HIERARCHY.get(user.role, {}).get("scope", "own")
        if user_scope not in scopes and role_level(user.role) < 99:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user
    return checker

def require_any_manager(user: User = Depends(get_current_user)) -> User:
    """Passes for manager, bu_head, business_head, ceo, super_admin, hr."""
    if role_level(user.role) < 20 and user.role not in ("hr", "finance"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Management role required")
    return user
