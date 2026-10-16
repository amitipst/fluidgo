"""Pure helpers for the rep-wise pipeline forecast sheet (no DB access, unit-testable)."""
from __future__ import annotations
from datetime import date, datetime
from typing import Iterable, Optional

CLOSED = {"closed_won", "closed_lost", "dropped"}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(d) -> Optional[str]:
    """'Oct 2026' from a date/datetime; None if missing."""
    if not d:
        return None
    return f"{_MONTHS[d.month - 1]} {d.year}"


def num(v) -> float:
    return float(v) if v is not None else 0.0


def target_label(stage: str, eta, note: Optional[str], outcome_at=None, competitor: Optional[str] = None) -> str:
    """What the Target Month cell shows for a deal's current state."""
    if stage == "closed_won":
        m = month_label(outcome_at)
        return f"Closed in {m.split()[0]}" if m else "Closed"
    if stage == "closed_lost":
        return f"Lost to {competitor}" if competitor else "Lost"
    if stage == "dropped":
        return "Dropped"
    if stage == "on_hold":
        return "Hold"
    if note and note.strip():
        return note.strip()
    return month_label(eta) or "—"


def effective_probability(stage: str, win_probability: Optional[int]) -> Optional[int]:
    """Rep's own number; a won deal is 100. Never invents a figure for open deals."""
    if stage == "closed_won":
        return 100
    if stage in ("closed_lost", "dropped"):
        return 0
    return win_probability


def amounts(recurring, one_time, deal_value) -> dict:
    """ARR, one-time and total. Older deals only have deal_value: it shows as the total."""
    arr, once = num(recurring), num(one_time)
    if recurring is None and one_time is None:
        return {"arr": 0.0, "one_time": 0.0, "total": num(deal_value)}
    return {"arr": arr, "one_time": once, "total": arr + once}


def status_of(stage: str) -> str:
    if stage == "closed_won":
        return "won"
    if stage in ("closed_lost", "dropped"):
        return "lost"
    if stage == "on_hold":
        return "hold"
    return "open"


def _superseded(history: Iterable[str], current: str) -> list:
    """Earlier targets in order, skipping repeats and any that equals today's target."""
    out: list = []
    for h in history:
        if h and h != current and (not out or out[-1] != h):
            out.append(h)
    return out


def build_row(deal, history: Iterable[str] = ()) -> dict:
    amt = amounts(deal.recurring_revenue, deal.one_time_revenue, deal.deal_value)
    prob = effective_probability(deal.stage, deal.win_probability)
    current = target_label(deal.stage, deal.closure_eta, deal.target_note,
                           deal.outcome_recorded_at or deal.updated_at, deal.outcome_competitor)
    return {
        "id": str(deal.id),
        "company": deal.company,
        "stage": deal.stage,
        "status": status_of(deal.stage),
        **amt,
        "win_probability": prob,
        "weighted": round(amt["total"] * prob / 100, 2) if prob is not None and deal.stage not in ("closed_lost", "dropped") else 0.0,
        "target": current,
        "closure_eta": deal.closure_eta.isoformat() if deal.closure_eta else None,
        "target_note": deal.target_note,
        "history": _superseded(history, current),
    }


def _sum(rows: list[dict]) -> dict:
    live = [r for r in rows if r["status"] in ("open", "hold", "won")]
    return {
        "count": len(rows),
        "arr": sum(r["arr"] for r in live),
        "one_time": sum(r["one_time"] for r in live),
        "total": sum(r["total"] for r in live),
        "weighted": sum(r["weighted"] for r in live),
    }


def group_by_rep(rows_with_owner: list[tuple[str, str, dict]]) -> dict:
    """rows_with_owner: (rep_id, rep_name, row). Reps sorted by name, rows keep input order.
    Totals exclude lost/dropped deals (they stay visible but do not count)."""
    groups: dict[str, dict] = {}
    for rep_id, rep_name, row in rows_with_owner:
        g = groups.setdefault(rep_id, {"rep_id": rep_id, "rep_name": rep_name, "rows": []})
        g["rows"].append(row)
    out = sorted(groups.values(), key=lambda g: (g["rep_name"] or "").lower())
    for g in out:
        g["totals"] = _sum(g["rows"])
    return {"groups": out, "totals": _sum([r for g in out for r in g["rows"]])}
