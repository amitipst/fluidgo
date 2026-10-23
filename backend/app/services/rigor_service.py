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


# ── Component breakdown (added 2026-10-23, Amit: "i want to see monthly
# weekly rigor scope of each individual and what can be done to improve the
# rigor score, as this can be a parameter for FGA/variable pay as well") ──
# Rules-based rather than AI-generated, deliberately: this score already
# feeds a compensation-linked FGA metric (activity.rigor_avg, Scoring
# Admin), so "what's dragging it down" needs to be a deterministic function
# of the same formula above, not a model's guess that could vary run to run
# or need separate hallucination/confidence handling for something tied to
# pay. Mirrors calculate_rigor_score's own per-component caps exactly —
# whenever that formula changes, this breakdown changes with it, by
# construction, instead of needing to be kept in sync by hand.
RIGOR_COMPONENT_MAX = {
    "visits": 15, "calls": 25, "followups": 30, "new_leads": 20, "proposals": 10,
}
RIGOR_COMPONENT_LABEL = {
    "visits": "Visits", "calls": "Calls", "followups": "Follow-ups",
    "new_leads": "New leads", "proposals": "Proposals",
}

def rigor_component_breakdown(dsr: DSRDaily) -> dict | None:
    """Per-component earned/max points for ONE standard working-day DSR row
    (same cap table as calculate_rigor_score's "Standard working day" branch).
    Returns None for exempt (leave/holiday), WFH and pre-sales rows — those
    use a different formula/cap table than the standard one FGA actually
    scores reps against, so a direct component comparison across mixed row
    types would be misleading rather than useful."""
    if dsr.status in ("leave", "holiday", "wfh"):
        return None
    if getattr(dsr, "dsr_type", "sales") == "presales":
        return None
    return {
        "visits":     min(dsr.visits * 15, 15),
        "calls":      min(dsr.calls * 5, 25),
        "followups":  min(dsr.followups * 3, 30),
        "new_leads":  min(dsr.new_leads * 10, 20),
        "proposals":  min(dsr.proposals * 10, 10),
    }


def aggregate_rigor_breakdown(dsrs: list) -> dict:
    """Averages rigor_component_breakdown() across a list of DSR rows (one
    person, one period) and names the single weakest component by how far
    its average earned-% falls below the others — the concrete "what can be
    done to improve it" lever, not just the overall number. Returns
    {"avg_rigor", "components": {key: {"earned_pct", "label"}}, "weakest": {...} | None}.
    `avg_rigor` reuses calculate_avg_rigor so it always matches the number
    shown elsewhere (DSR History, Team, FGA) for the same row set — this
    function never computes its own total, only the per-component split of it."""
    avg_rigor = calculate_avg_rigor(dsrs)
    breakdowns = [b for b in (rigor_component_breakdown(d) for d in dsrs) if b is not None]
    components: dict = {}
    for key, max_pts in RIGOR_COMPONENT_MAX.items():
        vals = [b[key] for b in breakdowns]
        earned_pct = round(100 * (sum(vals) / len(vals)) / max_pts, 1) if vals else 0.0
        components[key] = {"label": RIGOR_COMPONENT_LABEL[key], "earned_pct": earned_pct}

    weakest = None
    if breakdowns:
        weakest_key = min(components, key=lambda k: components[k]["earned_pct"])
        weakest = {
            "key": weakest_key,
            "label": RIGOR_COMPONENT_LABEL[weakest_key],
            "earned_pct": components[weakest_key]["earned_pct"],
        }
    return {"avg_rigor": avg_rigor, "components": components, "weakest": weakest, "days_counted": len(breakdowns)}


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
