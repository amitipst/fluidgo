"""Trend analytics — leads, wins, revenue and conversion over time.

Amit (2026-10-26): "reports and analysis should have weekly, monthly,
quarterly, annually, last 3 years etc. should be possible to see the trends of
wins, revenue, conversion, leads etc."

Pure functions only (no DB, no FastAPI) so every bucketing and ratio rule is
unit-tested; routers/trends.py fetches rows and calls build_trends().

Periods
-------
weekly     ISO week, Monday start            key "2026-10-19"
monthly    calendar month                    key "2026-10"
quarterly  India FY quarter (Apr-Mar year)   key "FY2026-Q3" (= Oct-Dec 2026)
yearly     India FY                          key "FY2026"    (= Apr 2026-Mar 2027)

India FY is used because period_service.py already documents it as the
company's analytics calendar ("India Financial Year: April 1 -> March 31").
NOTE the codebase is not yet consistent: scoring_engine._period_bounds (which
drives FGA revenue targets) uses *calendar* quarters/years. Trends follow
period_service; the discrepancy is flagged in claude/README.md Open Items
rather than silently changed, because FGA is compensation-linked.

Each series always contains every period in the window, zero-filled, so a
chart never hides a quiet week.

Definitions (stated, so nobody has to guess what a number means)
-------------------------------------------------------------------
leads_created      leads whose `date` falls in the period
lead_conversion    of the leads created in the period, the share that have since
                   become a deal (a *cohort* measure: older periods keep
                   maturing as their leads convert)
deals_created      deals created in the period; pipeline_added = their value
won_*              deals closed-won, dated by closure_eta, else the recorded
                   outcome date, else last update — closure_eta first so the
                   numbers agree with Revenue vs Target, the Executive Digest
                   and FGA, which all key on closure_eta
lost               closed-lost + dropped, dated by recorded outcome date first
win_rate           won / (won + lost) among deals that closed in the period
avg_deal_size      won revenue / won count
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from app.services.period_service import get_india_fy
from app.services.pipeline_sheet_service import amounts

GRANULARITIES = ("weekly", "monthly", "quarterly", "yearly")
DEFAULT_PERIODS = {"weekly": 12, "monthly": 12, "quarterly": 8, "yearly": 3}
MAX_PERIODS = {"weekly": 104, "monthly": 60, "quarterly": 20, "yearly": 10}
_IST = ZoneInfo("Asia/Kolkata")
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def to_date(v) -> Optional[date]:
    """date | datetime (naive = UTC, aware = converted to IST) -> date."""
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(_IST).date()
    return v


def _fy_quarter(d: date) -> tuple[int, int]:
    """(fy_start_year, quarter 1-4) for an India FY date."""
    fy = get_india_fy(d)
    q = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}[d.month]
    return fy, q


def period_key(d: date, g: str) -> str:
    if g == "weekly":
        return (d - timedelta(days=d.weekday())).isoformat()
    if g == "monthly":
        return f"{d.year}-{d.month:02d}"
    if g == "quarterly":
        fy, q = _fy_quarter(d)
        return f"FY{fy}-Q{q}"
    if g == "yearly":
        return f"FY{get_india_fy(d)}"
    raise ValueError(f"unknown granularity {g!r}")


def period_label(key: str, g: str) -> str:
    if g == "weekly":
        d = date.fromisoformat(key)
        return f"{d.day} {_MON[d.month - 1]}"
    if g == "monthly":
        y, m = key.split("-")
        return f"{_MON[int(m) - 1]} {y[2:]}"
    if g == "quarterly":
        fy, q = key[2:].split("-Q")
        return f"Q{q} FY{fy[2:]}-{str(int(fy) + 1)[2:]}"
    fy = int(key[2:])
    return f"FY {fy}-{str(fy + 1)[2:]}"


def _step_back(d: date, g: str) -> date:
    """A date inside the previous period."""
    if g == "weekly":
        return d - timedelta(days=7)
    first = d.replace(day=1)
    if g == "monthly":
        return first - timedelta(days=1)
    if g == "quarterly":
        qstart_month = {4: 4, 5: 4, 6: 4, 7: 7, 8: 7, 9: 7, 10: 10, 11: 10, 12: 10, 1: 1, 2: 1, 3: 1}[d.month]
        qstart = date(d.year, qstart_month, 1)
        return qstart - timedelta(days=1)
    fy = get_india_fy(d)
    return date(fy, 4, 1) - timedelta(days=1)


def period_keys(today: date, g: str, n: int) -> list[str]:
    """The last n periods ending with the one containing `today`, oldest first."""
    if g not in GRANULARITIES:
        raise ValueError(f"unknown granularity {g!r}")
    n = max(1, min(n, MAX_PERIODS[g]))
    keys, d = [], today
    for _ in range(n):
        keys.append(period_key(d, g))
        d = _step_back(d, g)
    return list(reversed(keys))


def window_start(today: date, g: str, n: int) -> date:
    """First day covered by the series — used to bound the DB queries."""
    first = period_keys(today, g, n)[0]
    if g == "weekly":
        return date.fromisoformat(first)
    if g == "monthly":
        y, m = first.split("-")
        return date(int(y), int(m), 1)
    if g == "quarterly":
        fy, q = first[2:].split("-Q")
        fy, q = int(fy), int(q)
        month = {1: 4, 2: 7, 3: 10, 4: 1}[q]
        return date(fy + 1 if q == 4 else fy, month, 1)
    return date(int(first[2:]), 4, 1)


def won_date(deal) -> Optional[date]:
    """When the deal was WON: the customer's email/LOI/PO/agreement date, else
    (older deals) the expected closure date -> outcome date -> last update."""
    return to_date(getattr(deal, "won_at", None)) or to_date(deal.closure_eta) or to_date(deal.outcome_recorded_at) or to_date(deal.updated_at)


def lost_date(deal) -> Optional[date]:
    return to_date(deal.outcome_recorded_at) or to_date(deal.closure_eta) or to_date(deal.updated_at)


def _pct(num: float, den: float) -> Optional[float]:
    return round(num / den * 100, 1) if den else None


def build_trends(g: str, today: date, n: int, *, meetings: Iterable, leads: Iterable,
                 deals: Iterable) -> dict:
    """meetings: objects with .date; leads: .date, .converted_to_deal_id;
    deals: PipelineDeal-like (stage, created_at, closure_eta, outcome_recorded_at,
    updated_at, recurring_revenue, one_time_revenue, deal_value)."""
    keys = period_keys(today, g, n)
    rows = {k: {"period": k, "label": period_label(k, g), "meetings": 0, "leads_created": 0,
                "leads_converted": 0, "deals_created": 0, "pipeline_added": 0.0,
                "won_count": 0, "won_arr": 0.0, "won_one_time": 0.0, "won_revenue": 0.0,
                "lost_count": 0, "invoiced_count": 0, "invoiced_revenue": 0.0} for k in keys}

    def bump(d: Optional[date], field: str, by=1):
        if d is None:
            return
        r = rows.get(period_key(d, g))
        if r is not None:
            r[field] += by

    for m in meetings:
        bump(to_date(m.date), "meetings")
    for l in leads:
        d = to_date(l.date)
        bump(d, "leads_created")
        if l.converted_to_deal_id:
            bump(d, "leads_converted")
    awaiting_n, awaiting_value = 0, 0.0   # won in the window, tax invoice not raised yet
    for deal in deals:
        amt = amounts(deal.recurring_revenue, deal.one_time_revenue, deal.deal_value)
        bump(to_date(deal.created_at), "deals_created")
        bump(to_date(deal.created_at), "pipeline_added", amt["total"])
        if deal.stage == "closed_won":
            d = won_date(deal)
            bump(d, "won_count")
            bump(d, "won_arr", amt["arr"])
            bump(d, "won_one_time", amt["one_time"])
            bump(d, "won_revenue", amt["total"])
            # Revenue is recognised when the tax invoice is raised, not when the deal is won.
            inv = to_date(getattr(deal, "invoiced_at", None))
            if inv:
                bump(inv, "invoiced_count")
                bump(inv, "invoiced_revenue", amt["total"])
            elif d is not None and period_key(d, g) in rows:
                awaiting_n += 1
                awaiting_value += amt["total"]
        elif deal.stage in ("closed_lost", "dropped"):
            bump(lost_date(deal), "lost_count")

    series = []
    for k in keys:
        r = rows[k]
        r["lead_conversion_pct"] = _pct(r["leads_converted"], r["leads_created"])
        r["win_rate_pct"] = _pct(r["won_count"], r["won_count"] + r["lost_count"])
        r["avg_deal_size"] = round(r["won_revenue"] / r["won_count"], 2) if r["won_count"] else None
        for f in ("pipeline_added", "won_arr", "won_one_time", "won_revenue", "invoiced_revenue"):
            r[f] = round(r[f], 2)
        series.append(r)

    tot = {f: sum(r[f] for r in series) for f in (
        "meetings", "leads_created", "leads_converted", "deals_created", "pipeline_added",
        "won_count", "won_arr", "won_one_time", "won_revenue", "lost_count",
        "invoiced_count", "invoiced_revenue")}
    tot["lead_conversion_pct"] = _pct(tot["leads_converted"], tot["leads_created"])
    tot["win_rate_pct"] = _pct(tot["won_count"], tot["won_count"] + tot["lost_count"])
    tot["avg_deal_size"] = round(tot["won_revenue"] / tot["won_count"], 2) if tot["won_count"] else None
    tot["won_awaiting_invoice_count"] = awaiting_n
    tot["won_awaiting_invoice_value"] = round(awaiting_value, 2)
    return {"granularity": g, "periods": len(series), "series": series, "totals": tot,
            "from": window_start(today, g, n).isoformat(), "to": today.isoformat()}
