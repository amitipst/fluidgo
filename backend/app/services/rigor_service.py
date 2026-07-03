from app.models import DSRDaily, Meeting, Lead

# ── Daily Rigor Score (per DSR row) ──────────────────────────────────────────
# Max 100 points. Tuned to realistic FluidPro field-rep daily targets:
#   Visits ≥ 1      → full 15 pts (physical presence is highest-value activity)
#   Calls ≥ 5       → full 25 pts
#   Follow-ups ≥ 10 → full 30 pts (core discipline metric)
#   New leads ≥ 2   → full 20 pts
#   Proposals ≥ 1   → full 10 pts

def calculate_rigor_score(dsr: DSRDaily) -> int:
    """Rule-based rigor score — 0 to 100. Returns -1 for exempt days (leave/holiday).
    Pre-sales DSRs use a separate formula based on technical activities."""
    if dsr.status in ("leave", "holiday"):
        return -1  # Exempt — excluded from averages

    # ── Pre-Sales formula ────────────────────────────────────────────────────
    if getattr(dsr, 'dsr_type', 'sales') == 'presales':
        score = 0
        score += min(getattr(dsr,'demos_conducted',0) * 20, 20)        # Demo = highest value
        score += min(getattr(dsr,'pocs_conducted',0) * 25, 25)         # POC = highest value
        score += min(getattr(dsr,'proposals_supported',0) * 15, 30)    # Proposal support
        score += min(getattr(dsr,'tech_discussions',0) * 5, 15)        # Tech discussions
        score += min((getattr(dsr,'workshops_conducted',0) +
                      getattr(dsr,'trainings_delivered',0)) * 10, 10)  # Sessions delivered
        return min(int(score), 100)

    # ── WFH formula ──────────────────────────────────────────────────────────
    if dsr.status == "wfh":
        score = 0
        score += min(dsr.virtual_meetings * 10, 15)
        score += min(dsr.calls * 5, 25)
        score += min(dsr.followups * 3, 30)
        score += min(dsr.new_leads * 10, 20)
        score += min(dsr.proposals * 10, 10)
        return min(int(score), 100)

    # ── Standard working day ─────────────────────────────────────────────────
    score = 0
    score += min(dsr.visits * 15, 15)
    score += min(dsr.calls * 5, 25)
    score += min(dsr.followups * 3, 30)
    score += min(dsr.new_leads * 10, 20)
    score += min(dsr.proposals * 10, 10)
    return min(int(score), 100)


def calculate_avg_rigor(dsrs: list) -> float:
    """Average rigor across a list of DSR rows — excludes exempt days (-1).
    Use this everywhere an average is needed, not a manual sum/divide."""
    eligible = [calculate_rigor_score(d) for d in dsrs if d.status not in ("leave", "holiday")]
    if not eligible:
        return 0.0
    return round(sum(eligible) / len(eligible), 1)


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
    """Rule-based lead quality score — 0 to 100."""
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
