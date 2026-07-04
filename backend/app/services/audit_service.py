"""
Audit service — call audit() from any router to log a user action.
Designed to be non-blocking: fire-and-forget via BackgroundTasks.

Usage in a router:
    from app.services.audit_service import audit
    from fastapi import BackgroundTasks, Request

    @router.post("/dsr")
    async def submit_dsr(
        body: DSRIn,
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
    ):
        dsr = ... # do the work
        background_tasks.add_task(audit, db, user, "CREATE", "dsr",
                                   str(dsr.id), f"DSR submitted for {body.date}",
                                   request=request)
        return dsr
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional, Any
import uuid
import logging

log = logging.getLogger(__name__)


async def audit(
    db: AsyncSession,
    user: Any,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    summary: Optional[str] = None,
    diff: Optional[dict] = None,
    request: Any = None,
):
    """Record an audit log entry. Always call via background_tasks.add_task()."""
    try:
        from app.models.audit import AuditLog
        ip = None
        ua = None
        if request:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent", "")[:500]

        entry = AuditLog(
            user_id=user.id,
            user_email=user.email,
            user_role=user.role,
            user_bu=getattr(user, "bu", None),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            diff=diff,
            ip_address=ip,
            user_agent=ua,
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        log.warning(f"Audit log failed (non-fatal): {e}")


async def get_audit_trail(
    db: AsyncSession,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    bu: Optional[str] = None,
    action: Optional[str] = None,
    since_hours: int = 168,   # default 7 days
    limit: int = 100,
) -> list:
    from app.models.audit import AuditLog
    from sqlalchemy import select, and_

    q = select(AuditLog).where(
        AuditLog.created_at >= datetime.utcnow() - timedelta(hours=since_hours)
    )
    if entity_type: q = q.where(AuditLog.entity_type == entity_type)
    if entity_id:   q = q.where(AuditLog.entity_id == entity_id)
    if user_id:     q = q.where(AuditLog.user_id == uuid.UUID(user_id))
    if bu:          q = q.where(AuditLog.user_bu == bu)
    if action:      q = q.where(AuditLog.action == action)

    q = q.order_by(AuditLog.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    return [{
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
    } for r in rows]
