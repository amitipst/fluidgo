from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database import get_db
from app.models import User
from app.services.deps import get_current_user
from app.services.permission_service import resolve_visible_user_ids
from app.services.deal_health_service import calculate_deal_health, deal_health_label
from app.services.ai_service import analyse
from app.repositories import opportunity_repo

router = APIRouter()


def _serialize(d) -> dict:
    return {c.name: getattr(d, c.name) for c in d.__table__.columns}


@router.get("")
async def list_opportunities(practice: Optional[str] = None, oem: Optional[str] = None,
                             risk_level: Optional[str] = None,
                             db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    visible = await resolve_visible_user_ids(db, user)
    deals = await opportunity_repo.list_opportunities(db, user_ids=visible, practice=practice,
                                                        oem=oem, risk_level=risk_level)
    return [_serialize(d) for d in deals]


@router.get("/{deal_id}/health")
async def opportunity_health(deal_id: str, db: AsyncSession = Depends(get_db),
                             user: User = Depends(get_current_user)):
    deal = await opportunity_repo.get_opportunity(db, deal_id)
    if not deal:
        raise HTTPException(404, "Opportunity not found")

    score = calculate_deal_health(deal)
    label = deal_health_label(score)
    deal.ai_deal_health = score
    deal.ai_deal_health_label = label
    await db.commit()

    context = f"""Deal: {deal.company}
Stage: {deal.stage} | Deal Value: {deal.deal_value or 'unknown'} | Deal Health: {score}/100 ({label})
Roadblock: {'Yes' if deal.roadblock else 'No'} | Risk Level: {deal.risk_level or 'unknown'}
Budget Status: {deal.budget_status or 'unknown'} | Timeline Status: {deal.timeline_status or 'unknown'}
Decision Maker: {deal.decision_maker or 'Not identified'}
Competition: {deal.competition or 'None noted'}
Last Update: {deal.todays_update or 'None'}"""
    recommendation = await analyse(context, prompt_type="deal_health")
    return {"score": score, "label": label, "recommendation": recommendation}
