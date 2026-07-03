"""FGA Approval Workflow router.

Lifecycle:
  1. BU Head (or cron) triggers score freeze for a period → status = 'pending_manager'
  2. Manager reviews each rep's breakdown and approves or disputes
     → status = 'pending_hr'
  3. HR reviews all (can override with reason) → status = 'pending_vp'
  4. VP/Finance approves final scores → status = 'approved'
     (or rejects back to 'disputed')
  5. Finance exports approved scores (CSV / JSON) for payroll

All state transitions are audit-logged in fga_approval_log.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User
from app.services.deps import get_current_user, require_role
from app.repositories import scoring_repo

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class FreezeRequest(BaseModel):
    period: str                     # "2026-07"
    template_ids: list[str] = []    # empty = all active templates

class ReviewAction(BaseModel):
    action: Literal["approve", "dispute", "override"]
    comment: Optional[str] = None
    override_score: Optional[float] = None   # HR only

class ExportRequest(BaseModel):
    period: str
    format: Literal["json", "csv"] = "json"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Freeze — BU Head triggers month-end score computation & locks
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/freeze")
async def freeze_period(body: FreezeRequest, db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_role("bu_head"))):
    """Compute and freeze FGA scores for all active reps in the period.
    Once frozen, scores are cached in scoring_results with status='pending_manager'.
    Idempotent — calling again refreshes unfrozen rows only."""
    from app.services.scoring_engine import compute_score
    from app.models import ScoringResult, ScoringTemplate

    # Get all active non-BU-Head users in this BU
    reps = (await db.execute(
        select(User).where(
            User.bu == user.bu,
            User.is_active == True,
            User.role != "bu_head"
        )
    )).scalars().all()

    frozen = []
    for rep in reps:
        result = await compute_score(db, rep, body.period)
        if result.get("score") is None:
            continue  # no template mapped — skip
        # Write/update scoring_result with pending status
        # v2: scope to template_id to avoid MultipleResultsFound across templates
        existing = (await db.execute(
            select(ScoringResult).where(
                ScoringResult.user_id == rep.id,
                ScoringResult.template_id == uuid.UUID(result["template_id"]),
                ScoringResult.period == body.period
            ).limit(1)
        )).scalar_one_or_none()
        if existing and existing.approval_status not in (None, "pending_manager"):
            # Already past manager review — don't overwrite
            frozen.append({"user_id": str(rep.id), "name": rep.name,
                           "score": float(existing.score), "status": existing.approval_status,
                           "skipped": True})
            continue
        if existing:
            existing.score = result["score"]
            existing.breakdown = result["breakdown"]
            existing.computed_at = datetime.utcnow()
            existing.approval_status = "pending_manager"
        else:
            db.add(ScoringResult(
                user_id=rep.id,
                template_id=uuid.UUID(result["template_id"]),
                period=body.period,
                score=result["score"],
                breakdown=result.get("breakdown"),
                approval_status="pending_manager",
                computed_at=datetime.utcnow()
            ))
        frozen.append({"user_id": str(rep.id), "name": rep.name,
                       "score": result["score"], "status": "pending_manager"})

    await db.commit()
    return {"period": body.period, "frozen": len(frozen), "results": frozen}


# ─────────────────────────────────────────────────────────────────────────────
# 2. List pending approvals (role-filtered)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pending")
async def list_pending(period: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Return all scoring results needing action from the current user's role."""
    from app.models import ScoringResult

    STATUS_FOR_ROLE = {
        "manager":      ["pending_manager"],
        "bu_head":      ["pending_manager", "pending_hr", "pending_vp", "disputed"],
        "hr":           ["pending_hr"],
        "vp":           ["pending_vp"],
        "finance":      ["approved"],          # finance sees approved for export
        "inside_sales": [],
        "rep":          [],
    }
    allowed_statuses = STATUS_FOR_ROLE.get(user.role, [])
    if not allowed_statuses:
        return []

    results = (await db.execute(
        select(ScoringResult).where(
            ScoringResult.period == period,
            ScoringResult.approval_status.in_(allowed_statuses)
        )
    )).scalars().all()

    out = []
    for r in results:
        rep = (await db.execute(select(User).where(User.id == r.user_id))).scalar_one_or_none()
        if not rep:
            continue
        # BU Head / Manager only see their BU
        if user.role in ("manager", "bu_head") and rep.bu != user.bu:
            continue
        out.append({
            "result_id": str(r.id),
            "user_id": str(rep.id), "name": rep.name,
            "role": rep.role, "bu": rep.bu,
            "period": r.period,
            "score": float(r.score),
            "breakdown": r.breakdown,
            "approval_status": r.approval_status,
            "manager_comment": r.manager_comment,
            "hr_comment": r.hr_comment,
            "override_score": float(r.override_score) if r.override_score else None,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 3. Manager approve / dispute
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{result_id}/manager-review")
async def manager_review(result_id: str, body: ReviewAction,
                         db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_role("manager", "bu_head"))):
    from app.models import ScoringResult
    r = await _get_result(db, result_id)
    if r.approval_status != "pending_manager":
        raise HTTPException(400, f"Cannot action: status is '{r.approval_status}'")
    r.approval_status = "pending_hr" if body.action == "approve" else "disputed"
    r.manager_comment = body.comment
    r.reviewed_by_manager_id = user.id
    r.manager_reviewed_at = datetime.utcnow()
    await db.commit()
    return {"result_id": result_id, "new_status": r.approval_status}


# ─────────────────────────────────────────────────────────────────────────────
# 4. HR review / override
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{result_id}/hr-review")
async def hr_review(result_id: str, body: ReviewAction,
                    db: AsyncSession = Depends(get_db),
                    user: User = Depends(require_role("bu_head"))):  # HR uses bu_head role for now
    from app.models import ScoringResult
    r = await _get_result(db, result_id)
    if r.approval_status not in ("pending_hr", "disputed"):
        raise HTTPException(400, f"Cannot action: status is '{r.approval_status}'")
    if body.action == "override" and body.override_score is not None:
        r.override_score = body.override_score
        r.approval_status = "pending_vp"
    elif body.action == "approve":
        r.approval_status = "pending_vp"
    else:
        r.approval_status = "disputed"
    r.hr_comment = body.comment
    r.reviewed_by_hr_id = user.id
    r.hr_reviewed_at = datetime.utcnow()
    await db.commit()
    return {"result_id": result_id, "new_status": r.approval_status,
            "effective_score": float(r.override_score or r.score)}


# ─────────────────────────────────────────────────────────────────────────────
# 5. VP / Finance final approval
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{result_id}/vp-approve")
async def vp_approve(result_id: str, body: ReviewAction,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_role("bu_head"))):
    from app.models import ScoringResult
    r = await _get_result(db, result_id)
    if r.approval_status != "pending_vp":
        raise HTTPException(400, f"Cannot action: status is '{r.approval_status}'")
    r.approval_status = "approved" if body.action == "approve" else "disputed"
    r.vp_comment = body.comment
    r.reviewed_by_vp_id = user.id
    r.vp_reviewed_at = datetime.utcnow()
    await db.commit()
    return {"result_id": result_id, "new_status": r.approval_status}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Export approved scores (Finance / HR)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/export")
async def export_approved(period: str, db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_role("bu_head", "manager"))):
    """Returns all approved FGA scores for a period — Finance downloads this."""
    from app.models import ScoringResult
    from fastapi.responses import StreamingResponse
    import csv, io

    results = (await db.execute(
        select(ScoringResult).where(
            ScoringResult.period == period,
            ScoringResult.approval_status == "approved"
        )
    )).scalars().all()

    rows = []
    for r in results:
        rep = (await db.execute(select(User).where(User.id == r.user_id))).scalar_one_or_none()
        if not rep:
            continue
        rows.append({
            "name": rep.name, "email": rep.email, "role": rep.role, "bu": rep.bu,
            "period": r.period,
            "fga_score": float(r.override_score or r.score),
            "raw_score": float(r.score),
            "overridden": r.override_score is not None,
            "manager_comment": r.manager_comment or "",
            "hr_comment": r.hr_comment or "",
            "vp_comment": r.vp_comment or "",
            "approved_at": r.vp_reviewed_at.isoformat() if r.vp_reviewed_at else "",
        })

    if not rows:
        return {"period": period, "count": 0, "data": []}

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fga_approved_{period}.csv"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_result(db: AsyncSession, result_id: str):
    from app.models import ScoringResult
    r = (await db.execute(
        select(ScoringResult).where(ScoringResult.id == uuid.UUID(result_id))
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Scoring result not found")
    return r
