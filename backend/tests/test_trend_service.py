"""Trend bucketing and ratios (v1.5.0). India FY quarters/years, zero-filled series."""
from datetime import date, datetime, timezone
from types import SimpleNamespace as NS

import pytest

from app.services import trend_service as t

MON = date(2026, 10, 26)   # a Monday, FY2026 Q3


# ── keys and labels ──────────────────────────────────────────────────────────
def test_weekly_key_is_the_monday():
    assert t.period_key(date(2026, 10, 25), "weekly") == "2026-10-19"   # Sunday -> previous Monday
    assert t.period_key(MON, "weekly") == "2026-10-26"


def test_monthly_key():
    assert t.period_key(date(2026, 1, 3), "monthly") == "2026-01"


@pytest.mark.parametrize("d,key", [
    (date(2026, 4, 1), "FY2026-Q1"), (date(2026, 6, 30), "FY2026-Q1"),
    (date(2026, 7, 1), "FY2026-Q2"), (date(2026, 10, 26), "FY2026-Q3"),
    (date(2026, 12, 31), "FY2026-Q3"), (date(2027, 1, 1), "FY2026-Q4"),
    (date(2027, 3, 31), "FY2026-Q4"), (date(2027, 4, 1), "FY2027-Q1"),
])
def test_quarterly_uses_india_fy(d, key):
    assert t.period_key(d, "quarterly") == key


def test_yearly_uses_india_fy():
    assert t.period_key(date(2026, 3, 31), "yearly") == "FY2025"
    assert t.period_key(date(2026, 4, 1), "yearly") == "FY2026"


def test_labels_are_readable():
    assert t.period_label("2026-10-19", "weekly") == "19 Oct"
    assert t.period_label("2026-10", "monthly") == "Oct 26"
    assert t.period_label("FY2026-Q3", "quarterly") == "Q3 FY26-27"
    assert t.period_label("FY2026", "yearly") == "FY 2026-27"


def test_unknown_granularity_raises():
    with pytest.raises(ValueError):
        t.period_key(MON, "daily")
    with pytest.raises(ValueError):
        t.period_keys(MON, "daily", 3)


# ── the window ───────────────────────────────────────────────────────────────
def test_period_keys_oldest_first_and_end_with_the_current_period():
    assert t.period_keys(MON, "weekly", 3) == ["2026-10-12", "2026-10-19", "2026-10-26"]
    assert t.period_keys(MON, "monthly", 3) == ["2026-08", "2026-09", "2026-10"]
    assert t.period_keys(MON, "quarterly", 3) == ["FY2026-Q1", "FY2026-Q2", "FY2026-Q3"]
    assert t.period_keys(MON, "yearly", 3) == ["FY2024", "FY2025", "FY2026"]


def test_period_keys_cross_a_year_boundary():
    assert t.period_keys(date(2027, 1, 15), "monthly", 3) == ["2026-11", "2026-12", "2027-01"]
    assert t.period_keys(date(2026, 2, 10), "quarterly", 3) == ["FY2025-Q2", "FY2025-Q3", "FY2025-Q4"]


def test_n_is_clamped():
    assert len(t.period_keys(MON, "yearly", 99)) == t.MAX_PERIODS["yearly"]
    assert len(t.period_keys(MON, "monthly", 0)) == 1


def test_default_presets_cover_what_amit_asked_for():
    assert t.DEFAULT_PERIODS["yearly"] == 3           # "last 3 years"
    assert set(t.GRANULARITIES) == {"weekly", "monthly", "quarterly", "yearly"}


@pytest.mark.parametrize("g,n,start", [
    ("weekly", 3, date(2026, 10, 12)), ("monthly", 12, date(2025, 11, 1)),
    ("quarterly", 8, date(2025, 1, 1)), ("yearly", 3, date(2024, 4, 1)),
])
def test_window_start(g, n, start):
    assert t.window_start(MON, g, n) == start


def test_ist_boundary_late_utc_evening_is_next_day_in_india():
    assert t.to_date(datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)) == date(2026, 10, 26)
    assert t.to_date(datetime(2026, 10, 25, 20, 0)) == date(2026, 10, 26)      # naive = UTC
    assert t.to_date(date(2026, 10, 25)) == date(2026, 10, 25)
    assert t.to_date(None) is None


# ── aggregation ──────────────────────────────────────────────────────────────
def lead(d, converted=False):
    return NS(date=d, converted_to_deal_id="x" if converted else None)


def deal(stage, created=date(2026, 10, 5), eta=None, outcome=None, arr=None, once=None, value=None):
    return NS(stage=stage, created_at=created, closure_eta=eta, outcome_recorded_at=outcome,
              updated_at=created, recurring_revenue=arr, one_time_revenue=once, deal_value=value)


def test_series_is_zero_filled_for_quiet_periods():
    out = t.build_trends("monthly", MON, 4, meetings=[], leads=[], deals=[])
    assert out["periods"] == 4 and len(out["series"]) == 4
    assert all(r["leads_created"] == 0 and r["won_revenue"] == 0 for r in out["series"])
    assert out["series"][0]["lead_conversion_pct"] is None      # no leads -> no ratio, not 0%
    assert out["series"][0]["win_rate_pct"] is None


def test_leads_conversion_and_meetings():
    out = t.build_trends("monthly", MON, 2,
                         meetings=[NS(date=date(2026, 10, 2)), NS(date=date(2026, 9, 9))],
                         leads=[lead(date(2026, 10, 1), True), lead(date(2026, 10, 9)),
                                lead(date(2026, 10, 10)), lead(date(2026, 9, 3))],
                         deals=[])
    sep, octo = out["series"]
    assert (sep["leads_created"], sep["leads_converted"], sep["meetings"]) == (1, 0, 1)
    assert (octo["leads_created"], octo["leads_converted"], octo["meetings"]) == (3, 1, 1)
    assert octo["lead_conversion_pct"] == 33.3
    assert out["totals"]["leads_created"] == 4 and out["totals"]["lead_conversion_pct"] == 25.0


def test_wins_revenue_split_win_rate_and_average():
    deals = [
        deal("closed_won", eta=date(2026, 10, 10), arr=1_000_000, once=500_000),
        deal("closed_won", eta=date(2026, 10, 12), value=300_000),          # legacy: total only
        deal("closed_lost", outcome=datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)),
        deal("dropped", outcome=datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)),
        deal("warm", arr=100_000, once=0),                                   # open: not a win
    ]
    octo = t.build_trends("monthly", MON, 1, meetings=[], leads=[], deals=deals)["series"][0]
    assert octo["won_count"] == 2 and octo["lost_count"] == 1 and octo["dropped_count"] == 1
    assert octo["won_arr"] == 1_000_000 and octo["won_one_time"] == 500_000
    assert octo["won_revenue"] == 1_800_000
    assert octo["win_rate_pct"] == 66.7        # dropped (disqualified) is not a loss: same rule as Win-Loss
    assert octo["avg_deal_size"] == 900_000
    assert octo["deals_created"] == 5 and octo["pipeline_added"] == 1_800_000 + 100_000


def test_a_win_is_dated_by_closure_eta_not_creation():
    d = deal("closed_won", created=date(2026, 6, 1), eta=date(2026, 10, 10), once=100)
    out = t.build_trends("monthly", MON, 6, meetings=[], leads=[], deals=[d])
    by = {r["period"]: r for r in out["series"]}
    assert by["2026-10"]["won_count"] == 1 and by["2026-06"]["won_count"] == 0
    assert by["2026-06"]["deals_created"] == 1


def test_rows_outside_the_window_are_ignored():
    out = t.build_trends("monthly", MON, 2, meetings=[NS(date=date(2020, 1, 1))],
                         leads=[lead(date(2020, 1, 1))], deals=[deal("closed_won", eta=date(2020, 1, 1), once=5)])
    assert out["totals"]["meetings"] == 0 and out["totals"]["leads_created"] == 0 and out["totals"]["won_revenue"] == 0


def test_quarterly_and_yearly_group_by_india_fy():
    deals = [deal("closed_won", eta=date(2026, 2, 1), once=100),    # FY2025 Q4
             deal("closed_won", eta=date(2026, 5, 1), once=200),    # FY2026 Q1
             deal("closed_won", eta=date(2026, 10, 1), once=400)]   # FY2026 Q3
    q = {r["period"]: r["won_revenue"] for r in t.build_trends("quarterly", MON, 4, meetings=[], leads=[], deals=deals)["series"]}
    assert q["FY2025-Q4"] == 100 and q["FY2026-Q1"] == 200 and q["FY2026-Q3"] == 400 and q["FY2026-Q2"] == 0
    y = {r["period"]: r["won_revenue"] for r in t.build_trends("yearly", MON, 3, meetings=[], leads=[], deals=deals)["series"]}
    assert y["FY2025"] == 100 and y["FY2026"] == 600


# ── won = customer commitment date; revenue = tax invoice date ───────────────
def won(won_at=None, invoiced_at=None, eta=None, once=100):
    d = deal("closed_won", eta=eta, once=once)
    d.won_at, d.invoiced_at = won_at, invoiced_at
    return d


def test_win_is_dated_by_the_customers_commitment_not_the_eta():
    d = won(won_at=date(2026, 9, 20), eta=date(2026, 10, 30))
    by = {r["period"]: r for r in t.build_trends("monthly", MON, 3, meetings=[], leads=[], deals=[d])["series"]}
    assert by["2026-09"]["won_count"] == 1 and by["2026-10"]["won_count"] == 0


def test_revenue_counts_in_the_month_the_tax_invoice_is_raised():
    d = won(won_at=date(2026, 9, 20), invoiced_at=date(2026, 10, 5), once=500_000)
    out = t.build_trends("monthly", MON, 3, meetings=[], leads=[], deals=[d])
    by = {r["period"]: r for r in out["series"]}
    assert by["2026-09"]["won_revenue"] == 500_000 and by["2026-09"]["invoiced_revenue"] == 0
    assert by["2026-10"]["invoiced_revenue"] == 500_000 and by["2026-10"]["invoiced_count"] == 1
    assert out["totals"]["won_awaiting_invoice_count"] == 0


def test_won_but_not_invoiced_is_reported_as_awaiting_invoice():
    d = won(won_at=date(2026, 10, 2), once=250_000)
    out = t.build_trends("monthly", MON, 3, meetings=[], leads=[], deals=[d])
    assert out["totals"]["invoiced_revenue"] == 0
    assert out["totals"]["won_awaiting_invoice_count"] == 1 and out["totals"]["won_awaiting_invoice_value"] == 250_000


def test_old_won_deals_without_dates_still_fall_back_to_eta():
    d = won(eta=date(2026, 10, 10))
    by = {r["period"]: r for r in t.build_trends("monthly", MON, 1, meetings=[], leads=[], deals=[d])["series"]}
    assert by["2026-10"]["won_count"] == 1
