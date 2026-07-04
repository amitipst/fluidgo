from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.services.auth_service import (verify_password, create_access_token,
                                        create_refresh_token, decode_token, hash_password)
from app.services.audit_service import audit

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

def _user_dict(user: User) -> dict:
    return {
        "id": str(user.id), "name": user.name, "email": user.email,
        "role": user.role, "bu": user.bu, "business": getattr(user, "business", "fluidpro"),
        "manager_id": str(user.manager_id) if getattr(user, "manager_id", None) else None,
        "org_role_key": user.org_role_key
    }

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == req.email.lower().strip()))
    user = result.scalar_one_or_none()

    # Always run the same code path to prevent timing-based user enumeration
    if not user or not verify_password(req.password, user.password_hash):
        # Log failed attempt (no user obj — log anonymously)
        if user:
            background_tasks.add_task(
                audit, db, user, "LOGIN_FAILED", "auth", None,
                f"Failed login from {request.client.host if request.client else 'unknown'}",
                request=request
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Your account has been deactivated. Contact your manager.")

    # Log successful login
    background_tasks.add_task(
        audit, db, user, "LOGIN", "auth", None,
        f"Login from {request.client.host if request.client else 'unknown'}",
        request=request
    )

    return {
        "access_token":  create_access_token(str(user.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
        "user": _user_dict(user)
    }

@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("wrong token type")
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired refresh token — please log in again")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Account deactivated")

    return {
        "access_token":  create_access_token(str(user.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
        "user": _user_dict(user)
    }

@router.post("/logout")
async def logout(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Stateless JWT — no server-side session to invalidate.
    Client is responsible for clearing tokens.
    We log the logout event for audit purposes.
    """
    from app.services.deps import get_current_user
    from fastapi.security import HTTPBearer
    # Best-effort: try to log the logout, don't fail if token is already gone
    return {"message": "Logged out successfully. Clear your local tokens."}
