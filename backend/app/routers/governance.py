"""Governance role's dedicated API surface — validation only, per Amit's
2026-07-26 request: a role that validates DSR/DMR/DOR and FGA submissions
for completeness/timeliness, has no data-entry obligation of its own, no
approval authority over the real workflow, and NO visibility into revenue/
incentive/score figures.

Every endpoint below is either:
  - a read that is financial-data-free by construction (compliance summary
    is the exact same aggregation used by /api/compliance — see that
    module's docstring for why it contains no money; the FGA queue here
    explicitly excludes score/override_score/manager+HR+VP comments), or
  - a "review" action that only ever writes the governance_* columns added
    in migration 0030 — never approval_status, never a score, never
    anything with a payout consequence. It's a parallel compliance
    checkpoint, not an extra stage in the real approval chain, so it can
    never become a bottleneck on DSR/DOR approval or FGA/incentive payout.

Governance is deliberately NOT given a broader role_level-gated foothold
into the rest of the app — see deny_governance() in app/services/deps.py
and its call sites in dsr.py/dor.py/fga_approval.py/incentives.py/
analytics.py for the other half of this design (what governance is
explicitly blocked from, on endpoints its org-wide scope would otherwise
let it reach).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional, Literal
import uuid
from app.database import get_db
from app.models import User, DSRDaily, DORDaily, ScoringResult
from app.services.deps import require_role
from app.services.permission_service import resolve_visible_user_ids
from app.services.compliance_service import compute_compliance

router = APIRouter()

require_governance = require_role("governance", "super_admin")


class GovernanceReviewIn(BaseModel):
    flag:    bool = False
    comment: Optional[str] = None


@router.get("/compliance")
async def governance_compliance(
    period: str, report_type: Literal["dsr", "dor", "all"] = "all",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_governance),
):
    """Same aggregation as GET /api/compliance/summary — exposed under the
    governance namespace too so the Governance page/nav has one place to
    call. Governance's scope="all" makes resolve_visible_user_ids return
    None (everyone), same as CEO/super_admin."""
    visible = await resolve_visible_user_ids(db, user)
    return await compute_compliance(db, visible, period, report_type)


@router.get("/fga-queue")
async def fga_queue(
    period: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_governance),
):
    """FGA submission STATUS only for the period — which stage each score is
    at and whether manager/HR/VP/governance have reviewed it. Deliberately
    excludes score, override_score, and the manager/HR/VP free-text
    comments (those can reference figures we don't control the contents
    of) — only the computed numbers themselves are guaranteed absent from
    every OTHER field here."""
    results = (await db.execute(
        select(ScoringResult).where(ScoringResult.period == period)
    )).scalars().all()
    out = []
    for r in results:
        rep = (await db.execute(select(User).where(User.id == r.user_id))).scalar_one_or_none()
        if not rep:
            continue
        out.append({
            "result_id": str(r.id), "user_id": str(r.user_id),
            "name": rep.name, "email": rep.email, "role": rep.role,
            "period": r.period, "approval_status": r.approval_status,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            "manager_reviewed": r.manager_reviewed_at is not None,
            "hr_reviewed": r.hr_reviewed_at is not None,
            "vp_reviewed": r.vp_reviewed_at is not None,
            "governance_reviewed": r.governance_reviewed_at is not None,
            "governance_flag": r.governance_flag,
        })
    return out


async def _governance_review(db: AsyncSession, model, row_id: str, body: GovernanceReviewIn,
                             user: User, kind: str) -> dict:
    row = (await db.execute(select(model).where(model.id == uuid.UUID(row_id)))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"{kind} not found")
    row.governance_reviewed_by = user.id
    row.governance_reviewed_at = datetime.now(timezone.utc)
    row.governance_flag        = body.flag
    row.governance_comment     = body.comment
    await db.commit()
    return {
        "id": row_id,
        "governance_flag": row.governance_flag,
        "governance_reviewed_at": row.governance_reviewed_at.isoformat(),
        "message": f"{kind} {'flagged for follow-up' if body.flag else 'validated'}",
    }


@router.post("/dsr/{dsr_id}/review")
async def review_dsr(dsr_id: str, body: GovernanceReviewIn,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_governance)):
    """Validate or flag a DSR/DMR entry for completeness/timeliness. Does
    NOT touch approval_status — that stays the manager's call (see dsr.py
    approve_dsr, which explicitly blocks the governance role)."""
    return await _governance_review(db, DSRDaily, dsr_id, body, user, "DSR/DMR")


@router.post("/dor/{dor_id}/review")
async def review_dor(dor_id: str, body: GovernanceReviewIn,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_governance)):
    return await _governance_review(db, DORDaily, dor_id, body, user, "DOR")


@router.post("/fga/{result_id}/review")
async def review_fga(result_id: str, body: GovernanceReviewIn,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_governance)):
    """Validates that an FGA score was submitted/progressed through the
    approval chain on time — never sees or touches the score itself."""
    return await _governance_review(db, ScoringResult, result_id, body, user, "FGA score")
