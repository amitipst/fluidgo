"""Export guard (v1.6.3) — one place that decides who may download data and records every download.

Policy (Amit, 27 Oct 2026): bulk data exports are for managers and above (plus finance, hr and
crm_admin, all of which are level >= 20); reps, inside sales and pre-sales cannot download. Every
export writes an `EXPORT` audit event (who, role, which report, filters, IP) so a departing or
rogue user's downloads are traceable, including a CRM admin's. Used as a route dependency:

    @router.get("/x.csv", dependencies=[Depends(export_guard("Report name"))])
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, role_level
from app.services.audit_service import audit
from app.services.deps import get_current_user

MIN_EXPORT_LEVEL = 20


def can_export(user) -> bool:
    """Level >= 20 (manager and above). Governance is excluded unless a report opts in."""
    return role_level(user.role) >= MIN_EXPORT_LEVEL


def export_guard(report: str, *, restrict: bool = True, allow_governance: bool = False):
    async def dep(request: Request, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)) -> None:
        if restrict:
            if user.role == "governance" and not allow_governance:
                raise HTTPException(403, "Downloads are not available for this role")
            if not can_export(user):
                raise HTTPException(403, "Downloads are available to managers and above")
        params = {k: v for k, v in request.query_params.items()}
        await audit(db, user, "EXPORT", "export", None, f"Downloaded: {report}",
                    diff={"report": report, "filters": params}, request=request)
    return dep
