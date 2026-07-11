"""
Period utilities for performance comparison analytics.
Supports: weekly, monthly, quarterly, yearly
India Financial Year: April 1 → March 31

CFY = Current Financial Year (e.g. Apr 2026 – Mar 2027)
PFY = Previous Financial Year (e.g. Apr 2025 – Mar 2026)
"""
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional


def get_india_fy(d: date) -> int:
    """Returns the starting year of India's FY for a given date.
    FY 2026-27 starts Apr 2026 → returns 2026."""
    return d.year if d.month >= 4 else d.year - 1


def fy_bounds(start_year: int):
    """Returns (start, end) for India FY starting in start_year."""
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def quarter_bounds(q: int, fy_start_year: int):
    """India FY quarters:
    Q1: Apr–Jun, Q2: Jul–Sep, Q3: Oct–Dec, Q4: Jan–Mar"""
    quarters = {
        1: ((4, 1),  (6, 30)),
        2: ((7, 1),  (9, 30)),
        3: ((10, 1), (12, 31)),
        4: ((1, 1),  (3, 31)),
    }
    start_m, start_d = quarters[q][0]
    end_m, end_d     = quarters[q][1]
    # Q4 belongs to the NEXT calendar year of the FY
    if q == 4:
        cal_year = fy_start_year + 1
    else:
        cal_year = fy_start_year
    return date(cal_year, start_m, start_d), date(cal_year, end_m, end_d)


def months_in_quarter(q: int, fy_start_year: int):
    """Returns the 3 (year, month) tuples that make up an India FY quarter.
    Q4 correctly rolls into the next calendar year (Jan-Mar)."""
    start, end = quarter_bounds(q, fy_start_year)
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def current_quarter(d: date) -> int:
    """Returns India FY quarter (1-4) for a date."""
    m = d.month
    if m in (4, 5, 6):   return 1
    if m in (7, 8, 9):   return 2
    if m in (10, 11, 12): return 3
    return 4  # Jan–Mar


def week_bounds(d: date):
    """Returns (monday, sunday) for the ISO week containing d."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def month_bounds(year: int, month: int):
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def parse_period(period_str: Optional[str], mode: str = "monthly"):
    """
    Parse period string for different modes:
    - monthly:   "2026-05"  → (start, end)
    - quarterly: "2026-Q1"  → (start, end), (pfy_start, pfy_end)
    - yearly:    "2026"     → (start, end) for FY 2026-27
    - weekly:    "2026-W28" → (start, end)

    Returns: {
        "current": (start, end),
        "previous": (start, end) | None,   # same period PFY
        "label": str,
        "fy_start": int,
    }
    """
    today = date.today()

    if mode == "weekly":
        if period_str and "W" in period_str:
            # e.g. "2026-W28"
            yr, w = period_str.split("-W")
            d = date.fromisocalendar(int(yr), int(w), 1)
        else:
            d = today
        start, end = week_bounds(d)
        py_start = start - timedelta(weeks=52)
        py_end   = end   - timedelta(weeks=52)
        return {
            "current":  (start, end),
            "previous": (py_start, py_end),
            "label":    f"Week {d.isocalendar()[1]}, {d.year}",
            "prev_label": f"Same week, {d.year - 1}",
            "fy_start": get_india_fy(d),
        }

    if mode == "quarterly":
        if period_str and "Q" in period_str:
            yr_s, q_s = period_str.split("-Q")
            fy_yr, q = int(yr_s), int(q_s)
        else:
            fy_yr = get_india_fy(today)
            q = current_quarter(today)
        start, end = quarter_bounds(q, fy_yr)
        py_start, py_end = quarter_bounds(q, fy_yr - 1)
        q_labels = {1:"Q1 (Apr–Jun)", 2:"Q2 (Jul–Sep)",
                    3:"Q3 (Oct–Dec)", 4:"Q4 (Jan–Mar)"}
        return {
            "current":  (start, end),
            "previous": (py_start, py_end),
            "label":    f"{q_labels[q]} FY {fy_yr}-{str(fy_yr+1)[2:]}",
            "prev_label": f"{q_labels[q]} FY {fy_yr-1}-{str(fy_yr)[2:]}",
            "fy_start": fy_yr,
            "quarter":  q,
        }

    if mode == "yearly":
        fy_yr = int(period_str) if period_str else get_india_fy(today)
        start, end = fy_bounds(fy_yr)
        py_start, py_end = fy_bounds(fy_yr - 1)
        return {
            "current":  (start, end),
            "previous": (py_start, py_end),
            "label":    f"FY {fy_yr}-{str(fy_yr+1)[2:]}",
            "prev_label": f"FY {fy_yr-1}-{str(fy_yr)[2:]}",
            "fy_start": fy_yr,
        }

    # Default: monthly
    if period_str:
        yr, mo = int(period_str[:4]), int(period_str[5:7])
    else:
        yr, mo = today.year, today.month
    start, end = month_bounds(yr, mo)
    # Same month previous year
    py_start, py_end = month_bounds(yr - 1, mo)
    # Previous month (MoM)
    prev_mo = mo - 1 if mo > 1 else 12
    prev_yr = yr if mo > 1 else yr - 1
    mom_start, mom_end = month_bounds(prev_yr, prev_mo)
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    return {
        "current":   (start, end),
        "previous":  (py_start, py_end),    # same month PFY
        "mom":       (mom_start, mom_end),  # previous month (MoM)
        "label":     f"{month_names[mo-1]} {yr}",
        "prev_label": f"{month_names[mo-1]} {yr-1}",
        "mom_label": f"{month_names[prev_mo-1]} {prev_yr}",
        "fy_start":  get_india_fy(start),
        "quarter":   current_quarter(start),
    }
