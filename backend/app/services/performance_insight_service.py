"""Rule-based "Performance Intelligence" for the Dashboard (v1.6.1).

Replaces the card that waited minutes for a local model. Same advice shape,
but every line is a deterministic rule over numbers fluidGo already holds:
the rep's rigor breakdown, DSR recency and their own deal radar findings.
No model call, no new infrastructure, instant, and any line can be challenged
("why does it say that?") because the rule and the numbers are in the text.

Pure function: the router loads the rows, this module only decides the words.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "good": 3}

# Concrete, measurable lever per rigor component (mirrors rigor_service's caps).
COMPONENT_ACTION = {
    "visits": "Plan at least one customer visit each working day (worth 15 points).",
    "calls": "Aim for 5 calls a day for the full 25 points.",
    "followups": "10 follow-ups a day earns the full 30 points; it is the biggest lever.",
    "new_leads": "Add 2 new leads a day for the full 20 points.",
    "proposals": "Send or progress one proposal a day for the full 10 points.",
}

# radar finding key -> (title template, action). {n} = how many of my deals/leads.
DEAL_RULES = {
    "past_eta": ("{n} of your deals are past their expected closure date",
                 "Re-date each one honestly or close it; a stale date overstates your forecast.", "high"),
    "stalled": ("{n} of your deals have had no activity for 14+ days",
                "Log a touch this week or move the deal to Hold.", "high"),
    "qualified_unconverted": ("{n} qualified leads are not yet deals",
                              "Convert them so the revenue shows in your forecast.", "high"),
    "no_next_step": ("{n} open deals have no next step",
                     "Add a dated next step to each; a deal without one has no momentum owner.", "medium"),
    "no_split": ("{n} deals are missing ARR / One-time",
                 "Enter both (0 is allowed) so the forecast and trends are reliable.", "medium"),
    "no_sp_stage": ("{n} open deals are not on the SP stage ladder",
                    "Open each one and choose its SP stage so it gets a stage-based win %.", "medium"),
    "stale_leads": ("{n} early-stage leads are older than the limit",
                    "Progress, park (Hold) or close each lead.", "medium"),
}


def _rigor_items(rigor: Optional[dict]) -> list:
    if not rigor or not rigor.get("days_counted"):
        return []
    avg = rigor.get("avg_rigor", 0.0)
    days = rigor["days_counted"]
    out = []
    if avg < 40:
        sev, title = "high", "Daily activity is well below the expected level"
    elif avg < 70:
        sev, title = "medium", "Daily activity is moderate; there is room to lift it"
    else:
        sev, title = "good", "Daily activity is on track"
    out.append({"key": "rigor", "severity": sev, "title": title,
                "detail": f"Average rigor {avg:.0f}/100 over your last {days} standard working days.",
                "action": "Keep the daily rhythm going." if sev == "good"
                else "Focus on the weakest component below; it is the quickest gain."})
    w = rigor.get("weakest")
    if w and avg < 70:
        out.append({"key": "rigor_weakest", "severity": "medium",
                    "title": f"Weakest component: {w['label']}",
                    "detail": f"You earn {w['earned_pct']:.0f}% of the points available for {w['label'].lower()}.",
                    "action": COMPONENT_ACTION.get(w["key"], "Raise this activity first.")})
    return out


def _dsr_item(last_dsr: Optional[date], today: date) -> list:
    if last_dsr is None:
        return [{"key": "dsr_gap", "severity": "medium", "title": "No daily sales report on record yet",
                 "detail": "Rigor and coaching are calculated from your DSRs.", "action": "Submit today's DSR."}]
    gap = (today - last_dsr).days
    if gap >= 5:
        sev = "high"
    elif gap >= 2:
        sev = "medium"
    else:
        return []
    return [{"key": "dsr_gap", "severity": sev, "title": f"No DSR submitted for {gap} days",
             "detail": f"Your last DSR is dated {last_dsr.isoformat()}.",
             "action": "Submit it now; missed days lower compliance and hide your activity."}]


def _deal_items(report: Optional[dict]) -> list:
    if not report:
        return []
    out = []
    for f in report.get("findings", []):
        rule = DEAL_RULES.get(f["key"])
        if not rule:
            continue
        title, action, sev = rule
        detail = f"Largest: {f['items'][0]['company']}" if f.get("items") else ""
        if f.get("value"):
            detail += (", " if detail else "") + f"₹{f['value'] / 1e5:.1f} L at stake"
        out.append({"key": f["key"], "severity": sev, "title": title.format(n=f["count"]),
                    "detail": detail, "action": action})
    return out


def build_insights(rigor: Optional[dict], last_dsr: Optional[date], today: date,
                   report: Optional[dict], limit: int = 6) -> dict:
    items = _rigor_items(rigor) + _dsr_item(last_dsr, today) + _deal_items(report)
    items.sort(key=lambda i: SEVERITY_RANK[i["severity"]])
    attention = [i for i in items if i["severity"] in ("high", "medium")]
    if not attention and not items:
        items = [{"key": "none", "severity": "good", "title": "Not enough activity data yet",
                  "detail": "Insights appear once you have DSRs and deals recorded.", "action": "Submit your DSR and add your deals."}]
    elif not attention:
        items.append({"key": "all_clear", "severity": "good", "title": "Nothing needs your attention right now",
                      "detail": "No stalled, past-date or incomplete deals found.", "action": "Keep the cadence."})
    headline = (f"{len([i for i in attention if i['severity'] == 'high'])} things need action, "
                f"{len([i for i in attention if i['severity'] == 'medium'])} to improve"
                if attention else "You are on track")
    return {"headline": headline, "items": items[:limit], "basis": "Rules over your DSRs, deals and leads. No AI model is called."}
