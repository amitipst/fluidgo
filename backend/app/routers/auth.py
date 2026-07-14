from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.services.auth_service import (verify_password, create_access_token,
                                        create_refresh_token, decode_token, hash_password,
                                        validate_password_policy)
from app.services.audit_service import audit
from app.services.deps import get_current_user

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

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

async def _user_dict(user: User, db: AsyncSession) -> dict:
    from app.services.permission_service import resolve_direct_report_ids
    direct_reports = await resolve_direct_report_ids(db, user)
    return {
        "id": str(user.id), "name": user.name, "email": user.email,
        "role": user.role, "bu": user.bu, "business": getattr(user, "business", "fluidpro"),
        "manager_id": str(user.manager_id) if getattr(user, "manager_id", None) else None,
        "org_role_key": user.org_role_key,
        # Dual-hat support (e.g. a business_head who also personally line-manages
        # a small team) — lets the frontend show a "My Team" toggle without a
        # separate 'manager' role. See permission_service.resolve_direct_report_ids.
        "has_direct_reports": len(direct_reports) > 0,
        # Forces the frontend straight to /change-password on login, before
        # anything else renders. Backend enforces this independently too
        # (deps.get_current_user) — this flag is for UX, not the security
        # boundary itself.
        "must_change_password": getattr(user, "must_change_password", False),
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

    # Pre-warm the AI dashboard insight so it's likely ready by the time the
    # user actually looks at it — never blocks this response either way.
    # Only for field roles (the analysis is based on DSR/meeting activity,
    # which BU-head-and-above roles don't generate, so it'd be near-empty
    # for them). Skips regeneration if a reasonably fresh one already exists.
    if user.role in ("rep", "inside_sales", "pre_sales", "manager"):
        from app.routers.ai import generate_dashboard_insight
        from app.models import AIInsight
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=6)
        recent = (await db.execute(
            select(AIInsight).where(
                AIInsight.entity_type == "dashboard",
                AIInsight.entity_id == user.id,
                AIInsight.status == "ready",
                AIInsight.generated_at > cutoff,
            )
        )).scalar_one_or_none()
        if not recent:
            # Mark a pending row up front so if the user opens the dashboard
            # before generation finishes, it shows the spinner and polls the
            # existing job instead of kicking off a duplicate generation.
            existing = (await db.execute(
                select(AIInsight).where(
                    AIInsight.entity_type == "dashboard",
                    AIInsight.entity_id == user.id,
                )
            )).scalar_one_or_none()
            if existing:
                existing.status = "pending"
            else:
                db.add(AIInsight(entity_type="dashboard", entity_id=user.id,
                                  insight_type="daily_insight", status="pending"))
            await db.commit()
            background_tasks.add_task(generate_dashboard_insight, str(user.id))

    return {
        "access_token":  create_access_token(str(user.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
        "user": await _user_dict(user, db)
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
        "user": await _user_dict(user, db)
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


# ── Password reset (email link) ───────────────────────────────────────────────
import hashlib, secrets
from datetime import datetime, timedelta

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Sends a reset link IF the email belongs to an active account. Always
    returns the same response regardless — we never reveal whether an email
    is registered (prevents account enumeration)."""
    from app.models import PasswordResetToken
    from app.services.email_service import send_password_reset
    from app.config import settings

    email = body.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Only actually generate+send for active users, but respond identically either way.
    if user and user.is_active:
        raw_token = secrets.token_urlsafe(32)
        ttl = settings.RESET_TOKEN_TTL_MINUTES
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=ttl),
        ))
        await db.commit()
        reset_link = f"{settings.APP_BASE_URL}/reset-password?token={raw_token}"
        background_tasks.add_task(send_password_reset, user.email, user.name, reset_link, ttl)
        background_tasks.add_task(
            audit, db, user, "PASSWORD_RESET_REQUESTED", "auth", None,
            f"Reset requested for {email}", request=request
        )

    return {"message": "If that email is registered, a reset link has been sent. "
                       "Please check your inbox (and spam)."}

@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Consumes a valid, unused, unexpired token and sets the new password."""
    from app.models import PasswordResetToken

    token_hash = _hash_token(body.token)
    prt = (await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )).scalar_one_or_none()

    if not prt or prt.used_at is not None or prt.expires_at < datetime.utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired. "
                                 "Please request a new one.")

    user = (await db.execute(select(User).where(User.id == prt.user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(400, "Account not found or inactive.")

    policy_error = validate_password_policy(body.new_password, name=user.name, email=user.email)
    if policy_error:
        raise HTTPException(400, policy_error)

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.utcnow()
    prt.used_at = datetime.utcnow()
    # Invalidate any other outstanding tokens for this user
    others = (await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )).scalars().all()
    for o in others:
        if o.id != prt.id:
            o.used_at = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "PASSWORD_RESET_COMPLETED", "auth", None,
        f"Password reset for {user.email}", request=request
    )
    return {"message": "Your password has been reset. You can now sign in."}


# ── Self-service change password (logged in) ──────────────────────────────────
# This is the endpoint the forced first-login / post-admin-reset flow calls.
# Distinct from /reset-password above: this requires the CURRENT password
# (proves the person at the keyboard is actually the account holder, not
# just someone who intercepted a still-valid access token) rather than a
# emailed token. Both paths converge on the same policy check and both clear
# must_change_password, so neither can be used to dodge the other's rules.
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")

    policy_error = validate_password_policy(body.new_password, name=user.name, email=user.email)
    if policy_error:
        raise HTTPException(400, policy_error)

    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(400, "New password must be different from your current password.")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(
        audit, db, user, "PASSWORD_CHANGED", "auth", None,
        f"Password changed by {user.email}", request=request
    )
    return {"message": "Password updated."}
