from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database import get_db
from app.models import User
from app.services.deps import get_current_user, deny_governance
from app.services.permission_service import resolve_visible_user_ids
from app.services.deal_health_service import calculate_deal_health, deal_health_label
from app.services.ai_service import analyse
from app.repositories import opportunity_repo

from app.services.deal_rules_service import forecast_probability, deal_metrics, get_rules
router = APIRouter()


def _serialize(d) -> dict:
    return {c.name: getattr(d, c.name) for c in d.__table__.columns}


@router.get("")
async def list_opportunities(practice: Optional[str] = None, oem: Optional[str] = None,
                             risk_level: Optional[str] = None, business: Optional[str] = None,
                             include_archived: bool = False,
                             include_seed: bool = False,
                             db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    # Same reasoning as pipeline.py's list_deals — deal_value on every row,
    # org-wide once scope="all" resolves. Not part of what governance
    # validates, so blocked outright.
    deny_governance(user)
    from app.models import role_level
    visible = await resolve_visible_user_ids(db, user)
    # Seed-data opt-in gated to business_head+ — matches list_meetings()'s
    # convention (migration 0027) and pipeline.py's list_deals()/
    # loss_analysis() (migration 0029).
    show_seed = include_seed and role_level(user.role) >= 40
    deals = await opportunity_repo.list_opportunities(db, user_ids=visible, practice=practice,
                                                        oem=oem, risk_level=risk_level, business=business,
                                                        include_archived=include_archived,
                                                        include_seed=show_seed)
    # Compute the rule-based deal-health score up front for any deal missing it,
    # so the Opportunities cards always show a health indicator (the AI *coaching*
    # text still only generates on demand via /health — that's the slow part).
    dirty = False
    for d in deals:
        if d.ai_deal_health is None:
            d.ai_deal_health = calculate_deal_health(d)
            d.ai_deal_health_label = deal_health_label(d.ai_deal_health)
            dirty = True
    if dirty:
        await db.commit()

    # Attach each deal's owner business (added 2026-10-23, Amit: "opportunities
    # should show fluidpro") — one extra lookup query rather than a join on
    # the main list, since this is read-only display/filter-option data, not
    # part of the scoping query above. For a business_head this is always
    # their own single business (resolve_visible_user_ids already scoped
    # `visible` to it); for scope="all" roles (ceo/coo/crm_admin/governance)
    # it lets the frontend's filter dropdown — and a future second business
    # line (fluidprint/floxtax/hooks) — work the same way the `practice`
    # filter already does: populate its own options from what's in the data.
    owner_ids = {d.user_id for d in deals}
    biz_by_owner: dict = {}
    if owner_ids:
        rows = (await db.execute(select(User.id, User.business).where(User.id.in_(owner_ids)))).all()
        biz_by_owner = {uid: biz for uid, biz in rows}
    out = []
    rules = await get_rules(db)
    for d in deals:
        row = _serialize(d)
        row["business"] = biz_by_owner.get(d.user_id)
        # v1.5.0: one weighted-forecast probability shared with Pipeline and the digest
        row["forecast_probability"] = forecast_probability(d, rules)
        row.update(deal_metrics(d, rules))      # v1.6.1: same open/amount/win % as Deals and the radar
        out.append(row)
    return out


@router.get("/{deal_id}/health")
async def opportunity_health(deal_id: str, db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    deny_governance(user)
    deal = await opportunity_repo.get_opportunity(db, deal_id)
    if not deal:
        raise HTTPException(404, "Opportunity not found")

    score = calculate_deal_health(deal)
    label = deal_health_label(score)
    deal.ai_deal_health = score
    deal.ai_deal_health_label = label
    await db.commit()

    from app.services.pipeline_sheet_service import amounts
    effective_value = amounts(deal.recurring_revenue, deal.one_time_revenue, deal.deal_value)["total"]
    context = f"""Deal: {deal.company}
Stage: {deal.stage} | Deal Value: {effective_value or 'unknown'} | Deal Health: {score}/100 ({label})
Roadblock: {'Yes' if deal.roadblock else 'No'} | Risk Level: {deal.risk_level or 'unknown'}
Budget Status: {deal.budget_status or 'unknown'} | Timeline Status: {deal.timeline_status or 'unknown'}
Decision Maker: {deal.decision_maker or 'Not identified'}
Competition: {deal.competition or 'None noted'}
Last Update: {deal.todays_update or 'None'}"""
    recommendation = await analyse(context, prompt_type="deal_health")
    return {"score": score, "label": label, "recommendation": recommendation}
