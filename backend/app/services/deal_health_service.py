"""Rule-based Deal Health score — same philosophy as rigor_service.py: pure Python,
no LLM for the score itself. The LLM (via ai_service.py + prompts/deal_health.txt) is
only used for the qualitative recommendation text, kept separate on purpose (see the
risk register: Ollama is CPU-only and slow, so the score must never depend on it)."""
from datetime import datetime, timezone
from app.models import PipelineDeal

RISK_PENALTY = {"low": 0, "medium": 5, "high": 15, "critical": 30}


def calculate_deal_health(deal: PipelineDeal) -> int:
    score = int(deal.ai_closure_pct) if deal.ai_closure_pct is not None else 50

    if deal.last_activity_at:
        last = deal.last_activity_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_stale = (datetime.now(timezone.utc) - last).days
        if days_stale > 30:
            score -= 25
        elif days_stale > 14:
            score -= 10
    else:
        score -= 15  # no activity ever logged on this deal

    if deal.roadblock:
        score -= 15
    score -= RISK_PENALTY.get(deal.risk_level, 0)
    if deal.budget_status == "unconfirmed":
        score -= 10
    if deal.timeline_status == "delayed":
        score -= 10
    if not deal.decision_maker:
        score -= 5

    return max(0, min(100, score))


def deal_health_label(score: int) -> str:
    if score >= 80: return "healthy"
    if score >= 60: return "watch"
    if score >= 40: return "at_risk"
    return "critical"
