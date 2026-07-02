from datetime import date
from app.services.scoring_engine import _period_bounds


def test_period_bounds_month():
    assert _period_bounds("2026-07") == (date(2026, 7, 1), date(2026, 7, 31))


def test_period_bounds_month_leap_february():
    assert _period_bounds("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))


def test_period_bounds_quarter():
    assert _period_bounds("2026-Q3") == (date(2026, 7, 1), date(2026, 9, 30))


def test_period_bounds_quarter_spanning_year_end():
    assert _period_bounds("2026-Q4") == (date(2026, 10, 1), date(2026, 12, 31))


def test_period_bounds_year():
    assert _period_bounds("2026") == (date(2026, 1, 1), date(2026, 12, 31))
