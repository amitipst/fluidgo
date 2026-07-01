from app.models import DSRDaily, Meeting, Lead

def calculate_rigor_score(dsr: DSRDaily) -> int:
    """Rule-based rigor score — 0 to 100. No LLM needed."""
    if dsr.status in ("leave", "holiday"):
        return -1  # Exempt day
    score = 0
    score += min(dsr.visits * 10, 20)           # Max 20 — physical presence
    score += min(dsr.calls * 2, 20)             # Max 20 — outreach volume
    score += min(int(dsr.followups * 1.5), 30)  # Max 30 — follow-up discipline
    score += min(dsr.new_leads * 10, 20)        # Max 20 — pipeline building
    score += min(dsr.proposals * 5, 10)         # Max 10 — conversion activity
    return min(int(score), 100)

def bant_score(meeting: Meeting) -> dict:
    """BANT scoring — intent signal and closure probability."""
    bant = [meeting.bant_budget, meeting.bant_authority,
            meeting.bant_need, meeting.bant_timeline]
    filled = sum(1 for b in bant if b)
    pct_map = {4: 85, 3: 62, 2: 38, 1: 15, 0: 5}
    if filled == 4:
        intent = "hot"
    elif filled >= 3 and meeting.bant_need:
        intent = "hot"
    elif filled >= 2:
        intent = "warm"
    elif filled == 1 and meeting.opportunity:
        intent = "engaged"
    else:
        intent = "cold"
    return {
        "bant_filled": filled,
        "closure_pct": pct_map[filled],
        "intent": intent,
        "gaps": [label for label, val in zip(
            ["Budget", "Authority", "Need", "Timeline"], bant
        ) if not val]
    }

SOURCE_BASE_SCORE = {
    "Referral": 90, "Visit": 80, "Call": 60, "LinkedIn": 55, "Email": 50,
}

def score_lead(lead: Lead) -> int:
    """Rule-based lead quality score — 0 to 100. No LLM needed."""
    score = SOURCE_BASE_SCORE.get(lead.source, 50)
    if lead.requirement and len(lead.requirement.strip()) > 10:
        score += 5
    if lead.next_action:
        score += 5
    return min(int(score), 100)

def rigor_label(score: int) -> str:
    if score < 0:   return "exempt"
    if score >= 85: return "excellent"
    if score >= 70: return "good"
    if score >= 50: return "average"
    return "needs_improvement"
