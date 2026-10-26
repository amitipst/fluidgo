"""Weak-area radar for the Deals workspace (v1.6.0).

Amit (2026-10-26): "give good information to business leaders to work on weak
areas ... without hampering the performance and utility for sales team,
presales team, inside sales and delivery team."

Design rules (why this is shaped the way it is):

  * Rules-based and explainable, never an LLM call: every finding says what was
    measured, why it matters and what to do, so a leader can challenge it and a
    rep can act on it. (Compensation-adjacent numbers must be auditable; AI
    advice can be layered on top later, advisory only.)
  * One pass over rows the caller has already scoped (same visibility as the
    Pipeline list) - no per-deal queries, no per-row AI, O(n) in memory. The
    endpoint adds one deals query and one leads query, both indexed.
  * Pure function: no DB access here, so it is unit-tested without a database.
  * Role-aware output from one payload: `findings` + `reps` for leaders,
    `my_actions` for the owner (sales / inside sales), `presales_queue` for the
    presales owner, `renewals` for delivery / account managers.

Thresholds are defaults; override via feature_flags 'deal_rules' -> 'radar'.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from app.services import deal_rules_service as rules_svc
from app.services.deal_duplicate_service import is_open_deal, is_open_lead

DEFAULTS = {
    "stalled_days": 14,            # open deal with no activity this long
    "stale_lead_days": 21,         # early-stage lead this old and still not progressed
    "qualified_unconverted_days": 7,
    "won_uninvoiced_days": 30,     # won (order booked) but no invoice date after this long
    "concentration_pct": 40,       # one deal carrying this share of the weighted pipeline
    "renewal_window_days": 60,
    "sample": 8,                   # deals listed per finding
}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _days_since(dt, now: datetime) -> Optional[int]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days
    return (now.date() - dt).days


def _val(d) -> float:
    return float(d.deal_value) if getattr(d, "deal_value", None) is not None else 0.0


def _sp_idx(d) -> int:
    sp = getattr(d, "sp_stage", None)
    return rules_svc.STAGE_ORDER.index(sp) if sp in rules_svc.STAGE_ORDER else -1


def _item(d, names, detail: str) -> dict:
    return {"id": str(d.id), "type": "deal", "title": getattr(d, "title", None) or d.company,
            "company": d.company, "owner": names.get(d.user_id, ""), "detail": detail,
            "value": _val(d), "stage": rules_svc.sp_stage_label(d.sp_stage) if d.sp_stage else d.stage}


def _lead_item(l, names, detail: str) -> dict:
    return {"id": str(l.id), "type": "lead", "title": l.requirement or l.company, "company": l.company,
            "owner": names.get(l.user_id, ""), "detail": detail, "value": 0.0, "stage": l.stage or l.status}


def _finding(key, severity, title, why, action, items: list, sample: int) -> Optional[dict]:
    if not items:
        return None
    items = sorted(items, key=lambda i: -i["value"])
    return {"key": key, "severity": severity, "title": title, "why": why, "action": action,
            "count": len(items), "value": round(sum(i["value"] for i in items), 2), "items": items[:sample]}


def build_report(deals, leads, rules: dict, today: date, now: datetime, me_id=None,
                 names: Optional[dict] = None, thresholds: Optional[dict] = None) -> dict:
    t = {**DEFAULTS, **(thresholds or {})}
    names = names or {}
    n = t["sample"]
    open_deals = [d for d in deals if is_open_deal(d)]
    open_leads = [l for l in leads if is_open_lead(l)]

    # ── pipeline summary (open deals only) ───────────────────────────────────
    cats: dict[str, dict] = {c: {"count": 0, "value": 0.0, "weighted": 0.0} for c in ("pipeline", "best_case", "commit")}
    stages: dict[str, dict] = {k: {"count": 0, "value": 0.0} for k in rules_svc.STAGE_ORDER if k != "won"}
    open_value = weighted = 0.0
    prob_of = {}
    for d in open_deals:
        p = rules_svc.forecast_probability(d, rules) or 0
        prob_of[d.id] = p
        w = _val(d) * p / 100.0
        open_value += _val(d)
        weighted += w
        c = rules_svc.forecast_category(d, rules)
        if c in cats:
            cats[c]["count"] += 1; cats[c]["value"] += _val(d); cats[c]["weighted"] += w
        if d.sp_stage in stages:
            stages[d.sp_stage]["count"] += 1; stages[d.sp_stage]["value"] += _val(d)
    summary = {
        "open_count": len(open_deals), "open_value": round(open_value, 2), "weighted_value": round(weighted, 2),
        "by_category": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in cats.items()},
        "by_stage": [{"key": k, "label": rules_svc.sp_stage_label(k), **{kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()}} for k, v in stages.items()],
        "open_leads": len(open_leads),
    }

    # ── per-deal flags (computed once, reused by findings, reps and my_actions) ─
    flags: dict = {}
    for d in open_deals:
        f = []
        ds = _days_since(d.last_activity_at or d.created_at, now)
        if ds is not None and ds >= t["stalled_days"]:
            f.append(("stalled", f"No activity for {ds} days", "Log a touch or update the next step"))
        if d.closure_eta and d.closure_eta < today:
            f.append(("past_eta", f"Expected close {d.closure_eta.isoformat()} has passed", "Re-date the closure or close the deal"))
        if not (d.next_step or "").strip():
            f.append(("no_next_step", "No next step recorded", "Add the next step and its date"))
        if rules_svc.needs_revenue_split(d):
            f.append(("no_split", "ARR / One-time missing", "Enter ARR and One-time so the forecast is reliable"))
        flags[d.id] = f

    def collect(kind, severity, title, why, action):
        items = []
        for d in open_deals:
            for k, detail, _ in flags[d.id]:
                if k == kind:
                    items.append(_item(d, names, detail))
        return _finding(kind, severity, title, why, action, items, n)

    findings = [
        collect("past_eta", "high", "Deals past their expected closure date",
                "The forecast date is already wrong, so the month's number is overstated.",
                "Re-date each deal honestly or close it; do not carry stale dates."),
        collect("stalled", "high", f"Deals with no activity for {t['stalled_days']}+ days",
                "Silent deals rarely close; the longer the silence the lower the real win chance.",
                "Owner to log a touch this week or move the deal to Hold."),
        collect("no_next_step", "medium", "Open deals with no next step",
                "A deal without a dated next step has no momentum owner.",
                "Add a next step with a date on each."),
        collect("no_split", "medium", "Deals missing ARR / One-time",
                "Revenue mix and weighted forecast cannot be trusted for these.",
                "Complete both fields (0 is allowed)."),
    ]

    late = [d for d in open_deals if _sp_idx(d) >= 4]   # SP5+
    findings.append(_finding(
        "no_presales_owner", "medium", "Proposal-stage deals with no presales owner",
        "Deals at SP5+ need solution/BoQ support or the proposal slips.",
        "Assign a presales owner.",
        [_item(d, names, "No presales owner") for d in late if not d.presales_owner_id], n))
    findings.append(_finding(
        "no_decision_maker", "medium", "Negotiation-track deals with no decision maker",
        "SP6+ with no named decision maker or linked contact is single-threaded and risky.",
        "Name the decision maker or link the contact.",
        [_item(d, names, "No decision maker / contact") for d in open_deals
         if _sp_idx(d) >= 5 and not (d.decision_maker or "").strip() and not d.contact_id], n))

    # concentration risk
    if weighted > 0 and len(open_deals) >= 3:   # a 1-2 deal pipeline is trivially concentrated; not a signal
        top = max(open_deals, key=lambda d: _val(d) * prob_of.get(d.id, 0))
        share = _val(top) * prob_of.get(top.id, 0) / 100.0 / weighted * 100
        if share >= t["concentration_pct"]:
            findings.append(_finding(
                "concentration", "high", f"One deal carries {share:.0f}% of the weighted pipeline",
                "A single slip or loss would break the number.", "Build cover: add parallel qualified deals.",
                [_item(top, names, f"{share:.0f}% of weighted pipeline")], n))

    # leads (inside sales)
    qmin = rules.get("convert_min_stage", "sp4_qualification_bant")
    qi = rules_svc.STAGE_ORDER.index(qmin) if qmin in rules_svc.STAGE_ORDER else 3
    def lead_idx(l):
        return rules_svc.STAGE_ORDER.index(l.stage) if l.stage in rules_svc.STAGE_ORDER else -1
    findings.append(_finding(
        "qualified_unconverted", "high", "Qualified leads not yet converted to deals",
        "These passed qualification but are not in the pipeline - revenue that is invisible to the forecast.",
        "Convert them (or record why not).",
        [_lead_item(l, names, f"At {rules_svc.sp_stage_label(l.stage)} for {_days_since(l.date, now)} days")
         for l in open_leads if lead_idx(l) >= qi and (_days_since(l.date, now) or 0) >= t["qualified_unconverted_days"]], n))
    findings.append(_finding(
        "stale_leads", "medium", f"Early-stage leads older than {t['stale_lead_days']} days",
        "Leads that sit at SP1-SP3 lose interest; this is leakage at the top of the funnel.",
        "Progress, park (Hold) or close each one.",
        [_lead_item(l, names, f"Open {_days_since(l.date, now)} days at {rules_svc.sp_stage_label(l.stage)}")
         for l in open_leads if 0 <= lead_idx(l) <= 2 and (_days_since(l.date, now) or 0) >= t["stale_lead_days"]], n))

    # delivery / account management
    win = t["renewal_window_days"]
    findings.append(_finding(
        "renewals", "medium", f"Contract renewals / win-backs due in {win} days",
        "Farming revenue is cheapest to keep; these dates are approaching.",
        "Delivery and account owner to open the renewal conversation.",
        [_item(d, names, f"Re-engage by {d.reengage_at.isoformat()}") for d in deals
         if d.reengage_at and not d.reengage_done and not getattr(d, "archived", False)
         and 0 <= (d.reengage_at - today).days <= win], n))
    findings.append(_finding(
        "won_uninvoiced", "low", "Won deals with no invoice date yet",
        "Order is booked; Finance invoices in the ERP. Add the invoice date once raised so revenue trends are complete.",
        "Finance / owner to record the invoice date.",
        [_item(d, names, f"Won {d.won_at.isoformat()}, no invoice date") for d in deals
         if d.stage == "closed_won" and not d.invoiced_at and d.won_at
         and (_days_since(d.won_at, now) or 0) >= t["won_uninvoiced_days"]], n))

    findings = sorted([f for f in findings if f], key=lambda f: (SEVERITY_RANK[f["severity"]], -f["value"], -f["count"]))

    # ── people view for leaders ──────────────────────────────────────────────
    reps: dict = {}
    for d in open_deals:
        r = reps.setdefault(d.user_id, {"user_id": str(d.user_id), "name": names.get(d.user_id, ""), "open_count": 0,
                                         "open_value": 0.0, "weighted": 0.0, "stalled": 0, "past_eta": 0, "no_next_step": 0})
        r["open_count"] += 1; r["open_value"] += _val(d); r["weighted"] += _val(d) * prob_of.get(d.id, 0) / 100.0
        for k, _, _ in flags[d.id]:
            if k in ("stalled", "past_eta", "no_next_step"):
                r[k] += 1
    rep_rows = sorted(({**r, "open_value": round(r["open_value"], 2), "weighted": round(r["weighted"], 2),
                        "attention": r["stalled"] + r["past_eta"] + r["no_next_step"]} for r in reps.values()),
                      key=lambda r: (-r["attention"], -r["open_value"]))

    # ── "what should I do today" for the logged-in person ────────────────────
    my_actions = []
    for d in open_deals:
        if d.user_id == me_id and flags[d.id]:
            k, detail, action = sorted(flags[d.id], key=lambda x: ["past_eta", "stalled", "no_next_step", "no_split"].index(x[0]))[0]
            my_actions.append({**_item(d, names, detail), "action": action, "kind": k})
    my_actions.sort(key=lambda a: (["past_eta", "stalled", "no_next_step", "no_split"].index(a["kind"]), -a["value"]))
    presales_queue = [{**_item(d, names, "You are the presales owner"), "action": "Review scope / BoQ and update the proposal"}
                      for d in late if d.presales_owner_id == me_id and me_id is not None]

    headlines = []
    for f in findings[:3]:
        headlines.append(f"{f['count']} - {f['title'].lower()}" + (f" (₹{f['value']:,.0f})" if f["value"] else ""))
    return {"summary": summary, "findings": findings, "reps": rep_rows, "my_actions": my_actions[:10],
            "presales_queue": presales_queue[:10], "headlines": headlines, "thresholds": t}
