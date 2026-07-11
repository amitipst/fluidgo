"""Audit log query API — read-only, role-gated."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database import get_db
from app.models import User
from app.services.deps import require_level
from app.services.audit_service import get_audit_trail

router = APIRouter()

@router.get("")
async def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id:   Optional[str] = Query(None),
    user_id:     Optional[str] = Query(None),
    action:      Optional[str] = Query(None),
    since_hours: int           = Query(168, ge=1, le=8760),  # max 1 year
    limit:       int           = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_level(20))  # manager+
):
    """Return audit log entries filtered by the actor's scope.
    Business Head sees their whole business. Regional Manager/Manager see their own BU/team only."""
    bu = actor.bu if actor.role in ("manager", "regional_manager", "bu_head") else None
    # CEO/super_admin see everything (bu=None means no filter)
    if actor.role in ("ceo", "super_admin"):
        bu = None

    return await get_audit_trail(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        bu=bu,
        action=action,
        since_hours=since_hours,
        limit=limit,
    )
