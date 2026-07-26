"""DSR/DMR/DOR compliance dashboard — the direct fix for finding #4 in the
fluidGo data-quality review (no submission-rate/BU widget existed; the
2026-07-21 DSR-backfill work only laid groundwork via the submitted_late/
days_late flag on individual rows, not a rollup). See
app/services/compliance_service.py for the aggregation and the "why" this
is safe for the Governance role to reuse untouched (no financial figures
in the output at all).
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
import csv
import io
from app.database import get_db
from app.models import User
from app.services.deps import get_current_user, require_level
from app.services.permission_service import resolve_visible_user_ids
from app.services.compliance_service import compute_compliance

router = APIRouter()


@router.get("/summary")
async def compliance_summary(
    period: str,
    report_type: Literal["dsr", "dor", "all"] = "all",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20)),
):
    """Submission-rate-by-rep/BU widget. Scoped exactly like every other
    team endpoint via resolve_visible_user_ids — a manager sees their team,
    business_head+ sees more, the governance role (scope="all") sees
    everyone. No financial figures anywhere in the response."""
    visible = await resolve_visible_user_ids(db, user)
    return await compute_compliance(db, visible, period, report_type)


@router.get("/export")
async def compliance_export(
    period: str,
    report_type: Literal["dsr", "dor", "all"] = "all",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_level(20)),
):
    """CSV download of the compliance rollup — one of the three report/
    export gaps confirmed missing in the 2026-07-26 audit (Performance,
    Monthly DSR-for-teams, FGA). Reuses the exact download pattern already
    proven in FGAApproval.tsx/SystemHealth.tsx (blob → StreamingResponse)."""
    visible = await resolve_visible_user_ids(db, user)
    data = await compute_compliance(db, visible, period, report_type)
    rows = data["reps"]
    if not rows:
        return {"period": period, "count": 0, "data": []}

    fieldnames = [
        "name", "email", "role", "report_type", "region", "business",
        "expected_days", "submitted_days", "late_days", "compliance_pct",
        "consecutive_missed_days", "last_submitted_date", "at_risk",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=dsr_dmr_dor_compliance_{period}.csv"},
    )
