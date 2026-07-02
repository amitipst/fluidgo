from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import date
from app.database import get_db
from app.models import User, ScoringTemplate, ScoringParameter
from app.services.deps import get_current_user
from app.services.permission_service import require_org_role
from app.services import scoring_engine
from app.repositories import scoring_repo

router = APIRouter()

ADMIN_ROLES = ("admin", "super_admin", "practice_head")


class ParameterIn(BaseModel):
    name: str
    weight_pct: float
    metric_source: str
    calc_type: str = "pct"
    sort_order: int = 0


class TemplateIn(BaseModel):
    name: str
    role_key: str
    parameters: list[ParameterIn]


def _current_period() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _validate_weights(parameters: list[ParameterIn]):
    total = sum(p.weight_pct for p in parameters)
    if round(total) != 100:
        raise HTTPException(400, f"Parameter weights must sum to 100, got {total}")


@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_org_role(*ADMIN_ROLES))):
    result = await db.execute(select(ScoringTemplate))
    out = []
    for t in result.scalars().all():
        params = await scoring_repo.get_parameters(db, t.id)
        out.append({
            "id": str(t.id), "name": t.name, "role_key": t.role_key,
            "version": t.version, "is_active": t.is_active,
            "parameters": [{"id": str(p.id), "name": p.name, "weight_pct": float(p.weight_pct),
                             "metric_source": p.metric_source, "calc_type": p.calc_type,
                             "sort_order": p.sort_order} for p in params]
        })
    return out


@router.post("/templates")
async def create_template(body: TemplateIn, db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_org_role(*ADMIN_ROLES))):
    _validate_weights(body.parameters)
    existing = await scoring_repo.get_active_template(db, body.role_key)
    version = 1
    if existing:
        existing.is_active = False
        version = existing.version + 1
    tmpl = ScoringTemplate(name=body.name, role_key=body.role_key, version=version, is_active=True)
    db.add(tmpl)
    await db.flush()
    for p in body.parameters:
        db.add(ScoringParameter(template_id=tmpl.id, name=p.name, weight_pct=p.weight_pct,
                                 metric_source=p.metric_source, calc_type=p.calc_type, sort_order=p.sort_order))
    await db.commit()
    return {"id": str(tmpl.id), "role_key": tmpl.role_key, "version": tmpl.version}


@router.patch("/templates/{template_id}/parameters")
async def update_parameters(template_id: str, body: list[ParameterIn], db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_org_role(*ADMIN_ROLES))):
    _validate_weights(body)
    result = await db.execute(select(ScoringParameter).where(ScoringParameter.template_id == template_id))
    for existing in result.scalars().all():
        await db.delete(existing)
    await db.flush()
    for p in body:
        db.add(ScoringParameter(template_id=template_id, name=p.name, weight_pct=p.weight_pct,
                                 metric_source=p.metric_source, calc_type=p.calc_type, sort_order=p.sort_order))
    await db.commit()
    return {"template_id": template_id, "updated": True}


@router.get("/metrics")
async def list_available_metrics(user: User = Depends(require_org_role(*ADMIN_ROLES))):
    """Feeds a dropdown in ScoringAdmin.tsx so admins pick from real calculators
    instead of typing a metric_source string freehand."""
    return sorted(scoring_engine.METRIC_REGISTRY.keys())


@router.get("/my-score")
async def my_score(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return await scoring_engine.compute_score(db, user, period or _current_period())
