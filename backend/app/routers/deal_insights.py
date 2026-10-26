"""GET /api/deal-insights — weak-area radar for the Deals workspace (v1.6.0)."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lead, PipelineDeal, User, role_level
from app.services import deal_rules_service as rules_svc
from app.services import weak_area_service
from app.services.deps import deny_governance, get_current_user
from app.services.lead_stage_service import get_feature_flag
from app.services.permission_service import resolve_visible_user_ids

router = APIRouter()


@router.get("")
async def deal_insights(include_seed: bool = False, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Findings for exactly the deals/leads this user may already see (reps their
    own, managers their team, leaders their business). Read-only, rules-based."""
    deny_governance(user)
    visible = await resolve_visible_user_ids(db, user)
    seed = include_seed and role_level(user.role) >= 40
    dq = select(PipelineDeal).where(PipelineDeal.archived == False)  # noqa: E712
    lq = select(Lead)
    if visible is not None:
        dq = dq.where(PipelineDeal.user_id.in_(visible))
        lq = lq.where(Lead.user_id.in_(visible))
    if not seed:
        dq = dq.where(PipelineDeal.is_seed == False)  # noqa: E712
        lq = lq.where(Lead.is_seed == False)  # noqa: E712
    deals = (await db.execute(dq)).scalars().all()
    leads = (await db.execute(lq)).scalars().all()
    owner_ids = {d.user_id for d in deals} | {l.user_id for l in leads}
    names = {}
    if owner_ids:
        names = {uid: n for uid, n in (await db.execute(select(User.id, User.name).where(User.id.in_(owner_ids)))).all()}
    rules = await rules_svc.get_rules(db)
    flag = await get_feature_flag(db, rules_svc.DEAL_RULES_FLAG_KEY)
    radar_cfg = ((flag.config or {}).get("radar") if flag and flag.enabled and flag.config else None) or None
    now = datetime.now(timezone.utc)
    report = weak_area_service.build_report(deals, leads, rules, date.today(), now, user.id, names, radar_cfg)
    report["scope"] = "all" if visible is None else ("team" if len(visible) > 1 else "me")
    return report
