"""GET /api/performance-insights - the Dashboard's Performance Intelligence card (v1.6.1).

Rule-based and instant. Always about the logged-in person (their own DSRs, deals
and leads) so a manager sees their own coaching here and uses Team / Deals for
the people view. Replaces the card that depended on a local model."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DSRDaily, Lead, PipelineDeal, User
from app.services import deal_rules_service as rules_svc
from app.services import performance_insight_service as pis
from app.services import weak_area_service
from app.services.deps import deny_governance, get_current_user
from app.services.lead_stage_service import get_feature_flag
from app.services.rigor_service import aggregate_rigor_breakdown

router = APIRouter()


@router.get("")
async def performance_insights(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    deny_governance(user)
    dsrs = (await db.execute(
        select(DSRDaily).where(DSRDaily.user_id == user.id, DSRDaily.is_seed == False)  # noqa: E712
        .order_by(DSRDaily.date.desc()).limit(20))).scalars().all()
    deals = (await db.execute(
        select(PipelineDeal).where(PipelineDeal.user_id == user.id, PipelineDeal.archived == False,  # noqa: E712
                                   PipelineDeal.is_seed == False))).scalars().all()  # noqa: E712
    leads = (await db.execute(
        select(Lead).where(Lead.user_id == user.id, Lead.is_seed == False))).scalars().all()  # noqa: E712
    rules = await rules_svc.get_rules(db)
    flag = await get_feature_flag(db, "deal_rules")
    thresholds = ((flag.config or {}).get("radar") if flag and flag.enabled and flag.config else None) or None
    now = datetime.now(timezone.utc)
    report = weak_area_service.build_report(list(deals), list(leads), rules, date.today(), now, user.id,
                                            {user.id: user.name}, thresholds)
    rigor = aggregate_rigor_breakdown(list(dsrs)) if dsrs else None
    last_dsr = dsrs[0].date if dsrs else None
    out = pis.build_insights(rigor, last_dsr, date.today(), report)
    out["generated_at"] = now.isoformat()
    return out
