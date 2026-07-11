from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import date, datetime
import uuid
from app.database import get_db
from app.models import User, ScoringTemplate, ScoringParameter, ManualMetricEntry
from app.services.deps import get_current_user, require_level
from app.services import scoring_engine
from app.repositories import scoring_repo
from app.models import role_level

router = APIRouter()

# v3: scoring admin access = regional_manager (30) and above, plus explicit admin org_role_key
# ("bu_head" is the deprecated old name for regional_manager — same level 30, still covered by >= 30)
def _can_manage_scoring(user: User) -> bool:
    return role_level(user.role) >= 30 or user.org_role_key in ("admin","super_admin","practice_head")


class ParameterIn(BaseModel):
    name: str
    weight_pct: float
    metric_source: str
    calc_type: str = "pct"          # pct | tiered
    tiers: Optional[list] = None    # only for calc_type='tiered' — see ScoringParameter docstring
    is_active: bool = True
    sort_order: int = 0


class TemplateIn(BaseModel):
    name: str
    role_key: str
    parameters: list[ParameterIn]   # any length — 3, 5, 12, whatever the KRA set needs


def _current_period() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _validate_weights(parameters: list[ParameterIn]):
    # Only ACTIVE parameters need to sum to 100 — a disabled one can carry any
    # leftover weight without blocking save; re-enabling it later is exactly
    # when its weight (and everyone else's) needs revisiting.
    total = sum(p.weight_pct for p in parameters if p.is_active)
    if round(total) != 100:
        raise HTTPException(400, f"Active parameter weights must sum to 100, got {total}")


def _serialize_parameter(p: ScoringParameter) -> dict:
    return {
        "id": str(p.id), "name": p.name, "weight_pct": float(p.weight_pct),
        "metric_source": p.metric_source, "calc_type": p.calc_type,
        "tiers": p.tiers, "is_active": p.is_active, "sort_order": p.sort_order,
    }


@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    if not _can_manage_scoring(user):
        raise HTTPException(403, "Scoring admin requires regional_manager role or above")
    result = await db.execute(select(ScoringTemplate))
    out = []
    for t in result.scalars().all():
        params = await scoring_repo.get_parameters(db, t.id)
        out.append({
            "id": str(t.id), "name": t.name, "role_key": t.role_key,
            "version": t.version, "is_active": t.is_active,
            "parameters": [_serialize_parameter(p) for p in params]
        })
    return out


@router.post("/templates")
async def create_template(body: TemplateIn, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    if not _can_manage_scoring(user):
        raise HTTPException(403, "Scoring admin requires regional_manager role or above")
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
                                 metric_source=p.metric_source, calc_type=p.calc_type,
                                 tiers=p.tiers, is_active=p.is_active, sort_order=p.sort_order))
    await db.commit()
    return {"id": str(tmpl.id), "role_key": tmpl.role_key, "version": tmpl.version}


@router.patch("/templates/{template_id}/parameters")
async def update_parameters(template_id: str, body: list[ParameterIn], db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """Full replace — the list you send IS the new parameter set, any length.
    Add a row to introduce a new KRA, remove one to drop it, or just flip
    is_active on a row to pause/resume it without losing its config."""
    if not _can_manage_scoring(user):
        raise HTTPException(403, "Scoring admin requires regional_manager role or above")
    _validate_weights(body)
    result = await db.execute(select(ScoringParameter).where(ScoringParameter.template_id == template_id))
    for existing in result.scalars().all():
        await db.delete(existing)
    await db.flush()
    for p in body:
        db.add(ScoringParameter(template_id=template_id, name=p.name, weight_pct=p.weight_pct,
                                 metric_source=p.metric_source, calc_type=p.calc_type,
                                 tiers=p.tiers, is_active=p.is_active, sort_order=p.sort_order))
    await db.commit()
    return {"template_id": template_id, "updated": True}


@router.patch("/parameters/{parameter_id}/toggle")
async def toggle_parameter(parameter_id: str, db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """Quick enable/disable for one parameter — no weight-sum revalidation,
    so pausing a KRA never blocks on the rest of the template. Rebalancing
    weights (if wanted) happens via the main editor, on your own schedule."""
    if not _can_manage_scoring(user):
        raise HTTPException(403, "Scoring admin requires regional_manager role or above")
    param = (await db.execute(
        select(ScoringParameter).where(ScoringParameter.id == parameter_id)
    )).scalar_one_or_none()
    if not param:
        raise HTTPException(404, "Parameter not found")
    param.is_active = not param.is_active
    await db.commit()
    return {"id": str(param.id), "is_active": param.is_active}


@router.get("/metrics")
async def list_available_metrics(user: User = Depends(get_current_user)):
    """Feeds a dropdown in ScoringAdmin.tsx so admins pick from real calculators
    instead of typing a metric_source string freehand."""
    return sorted(scoring_engine.METRIC_REGISTRY.keys())


@router.get("/my-score")
async def my_score(period: Optional[str] = None, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return await scoring_engine.compute_score(db, user, period or _current_period())


# ─────────────────────────────────────────────────────────────────────────────
# Manual KPI entry — for metric_source values starting "manual." (no
# auto-calculator; sourced from systems fluidGo doesn't integrate with, e.g.
# invoicing/ticketing). Adding a new manual.* parameter in Scoring Admin
# automatically makes a new field appear here — no code change needed.
# ─────────────────────────────────────────────────────────────────────────────

async def _can_touch_manual_entry(db: AsyncSession, actor: User, target_user_id: str) -> bool:
    if str(actor.id) == target_user_id:
        return True
    if role_level(actor.role) < 20:
        return False
    from app.services.permission_service import resolve_visible_user_ids
    visible = await resolve_visible_user_ids(db, actor)
    return visible is None or uuid.UUID(target_user_id) in visible


class ManualEntryIn(BaseModel):
    user_id: str
    metric_key: str                     # must start with "manual."
    period: str
    value: float
    raw_inputs: Optional[dict] = None   # optional supporting numbers, for transparency/audit
    notes: Optional[str] = None


@router.get("/manual-entry/fields")
async def manual_entry_fields(role_key: str, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    """Returns the active template's manual.* parameters for role_key — drives
    the Monthly KPI Entry form dynamically. Add/remove/disable a parameter in
    Scoring Admin and this list changes automatically."""
    template = await scoring_repo.get_active_template(db, role_key)
    if not template:
        return []
    params = await scoring_repo.get_parameters(db, template.id)
    return [_serialize_parameter(p) for p in params
            if p.is_active and p.metric_source.startswith("manual.")]


@router.get("/manual-entry")
async def get_manual_entries(user_id: str, period: str, db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    """All manual entries already saved for user_id/period, keyed by metric_key
    — pre-fills the entry form so re-opening it shows last month's edits."""
    if not await _can_touch_manual_entry(db, user, user_id):
        raise HTTPException(403, "You cannot view KPI values for users outside your scope")
    rows = (await db.execute(
        select(ManualMetricEntry).where(
            ManualMetricEntry.user_id == uuid.UUID(user_id),
            ManualMetricEntry.period == period,
        )
    )).scalars().all()
    return {
        r.metric_key: {
            "value": float(r.value), "raw_inputs": r.raw_inputs, "notes": r.notes,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        } for r in rows
    }


@router.post("/manual-entry")
async def submit_manual_entry(body: ManualEntryIn, db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    """Upserts one metric's value for a period — call once per field on the
    Monthly KPI Entry form. Re-submitting the same (user, metric, period)
    corrects the value in place rather than creating duplicate history."""
    if not body.metric_key.startswith("manual."):
        raise HTTPException(400, "metric_key must start with 'manual.'")
    if not await _can_touch_manual_entry(db, user, body.user_id):
        raise HTTPException(403, "You cannot enter KPI values for users outside your scope")

    uid = uuid.UUID(body.user_id)
    existing = (await db.execute(
        select(ManualMetricEntry).where(
            ManualMetricEntry.user_id == uid,
            ManualMetricEntry.metric_key == body.metric_key,
            ManualMetricEntry.period == body.period,
        )
    )).scalar_one_or_none()
    now = datetime.utcnow()
    if existing:
        existing.value = body.value
        existing.raw_inputs = body.raw_inputs
        existing.notes = body.notes
        existing.entered_by = user.id
        existing.updated_at = now
    else:
        db.add(ManualMetricEntry(
            user_id=uid, metric_key=body.metric_key, period=body.period,
            value=body.value, raw_inputs=body.raw_inputs, notes=body.notes,
            entered_by=user.id, entered_at=now, updated_at=now,
        ))
    await db.commit()
    return {"user_id": body.user_id, "metric_key": body.metric_key,
            "period": body.period, "value": body.value}
