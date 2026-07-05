"""System Health + Audit Trail — super_admin only."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional
from datetime import datetime, timedelta
import csv, io, json

from app.database import get_db
from app.models import User, DSRDaily, AuditLog, role_level
from app.services.deps import get_current_user

router = APIRouter()

def _require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "super_admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Super Admin access required")
    return user

@router.get("/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_require_super_admin)
):
    """Real-time system health snapshot."""
    # User stats
    total_users  = (await db.execute(select(func.count()).select_from(User))).scalar()
    active_users = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar()

    # DSR today
    today = datetime.utcnow().date()
    dsrs_today = (await db.execute(
        select(func.count()).select_from(DSRDaily).where(DSRDaily.date == today)
    )).scalar()

    # Audit events last 24h
    since_24h = datetime.utcnow() - timedelta(hours=24)
    audit_24h = (await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= since_24h)
    )).scalar()

    # Login events last 24h
    logins_24h = (await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "LOGIN",
            AuditLog.created_at >= since_24h
        )
    )).scalar()

    # Failed login events last 24h
    failed_24h = (await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED",
            AuditLog.created_at >= since_24h
        )
    )).scalar()

    # Oldest audit log (retention check)
    oldest_log = (await db.execute(
        select(func.min(AuditLog.created_at))
    )).scalar()

    return {
        "timestamp":     datetime.utcnow().isoformat(),
        "users": {
            "total":     total_users,
            "active":    active_users,
            "inactive":  total_users - active_users,
        },
        "activity": {
            "dsrs_submitted_today": dsrs_today,
            "audit_events_24h":     audit_24h,
            "logins_24h":           logins_24h,
            "failed_logins_24h":    failed_24h,
        },
        "audit_retention": {
            "oldest_log": oldest_log.isoformat() if oldest_log else None,
            "policy_days": 90,
        }
    }

@router.get("/audit")
async def audit_trail(
    date_from:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:     Optional[str] = Query(None, description="YYYY-MM-DD"),
    action:      Optional[str] = Query(None),
    user_email:  Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit:       int           = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_require_super_admin)
):
    """Full audit trail — filterable by date, action, user, entity type."""
    q = select(AuditLog).order_by(AuditLog.created_at.desc())

    if date_from:
        q = q.where(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        # Include all of date_to
        end = datetime.fromisoformat(date_to) + timedelta(days=1)
        q = q.where(AuditLog.created_at < end)
    if action:
        q = q.where(AuditLog.action == action)
    if user_email:
        q = q.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)

    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()

    return [
        {
            "id":          str(r.id),
            "user_email":  r.user_email,
            "user_role":   r.user_role,
            "user_bu":     r.user_bu,
            "action":      r.action,
            "entity_type": r.entity_type,
            "entity_id":   r.entity_id,
            "summary":     r.summary,
            "ip_address":  r.ip_address,
            "created_at":  r.created_at.isoformat(),
        }
        for r in rows
    ]

@router.get("/audit/download")
async def download_audit_csv(
    date_from:   Optional[str] = Query(None),
    date_to:     Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_require_super_admin)
):
    """Download audit logs as CSV."""
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if date_from:
        q = q.where(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        end = datetime.fromisoformat(date_to) + timedelta(days=1)
        q = q.where(AuditLog.created_at < end)

    rows = (await db.execute(q)).scalars().all()

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp","user_email","role","bu","action",
                         "entity_type","entity_id","summary","ip_address"])
        for r in rows:
            writer.writerow([
                r.created_at.isoformat(), r.user_email, r.user_role, r.user_bu or "",
                r.action, r.entity_type, r.entity_id or "", r.summary or "",
                r.ip_address or ""
            ])
        yield output.getvalue()

    filename = f"fluidgo_audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/audit/purge")
async def purge_old_logs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_require_super_admin)
):
    """Purge audit logs older than 90 days. Returns count deleted."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    result = await db.execute(
        text("DELETE FROM audit_logs WHERE created_at < :cutoff RETURNING id"),
        {"cutoff": cutoff}
    )
    deleted = len(result.fetchall())
    await db.commit()
    return {"deleted": deleted, "cutoff": cutoff.isoformat()}
