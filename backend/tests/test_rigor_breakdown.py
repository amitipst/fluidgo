"""Tests for rigor_service's per-component breakdown (added 2026-10-23, Amit:
"i want to see monthly weekly rigor scope of each individual and what can be
done to improve the rigor score, as this can be a parameter for FGA/variable
pay as well"). Pure-function tests, same SimpleNamespace-fake-row pattern as
test_rigor_service.py — no DB needed."""
from types import SimpleNamespace as NS
from app.services.rigor_service import (
    rigor_component_breakdown, aggregate_rigor_breakdown, calculate_avg_rigor,
)


def dsr(**kw):
    base = dict(status="working", dsr_type="sales", virtual_meetings=0,
                visits=0, calls=0, followups=0, new_leads=0, proposals=0)
    base.update(kw)
    return NS(**base)


def test_component_breakdown_caps_match_calculate_rigor_score():
    # visits ≥1 -> 15, calls ≥5 -> 25, followups ≥10 -> 30, new_leads ≥2 -> 20, proposals ≥1 -> 10
    b = rigor_component_breakdown(dsr(visits=5, calls=20, followups=50, new_leads=10, proposals=5))
    assert b == {"visits": 15, "calls": 25, "followups": 30, "new_leads": 20, "proposals": 10}


def test_component_breakdown_partial_credit():
    b = rigor_component_breakdown(dsr(visits=0, calls=2, followups=3, new_leads=0, proposals=0))
    assert b == {"visits": 0, "calls": 10, "followups": 9, "new_leads": 0, "proposals": 0}


def test_component_breakdown_none_for_exempt_wfh_presales_rows():
    assert rigor_component_breakdown(dsr(status="leave")) is None
    assert rigor_component_breakdown(dsr(status="holiday")) is None
    assert rigor_component_breakdown(dsr(status="wfh")) is None
    assert rigor_component_breakdown(dsr(dsr_type="presales")) is None


def test_aggregate_breakdown_avg_rigor_matches_calculate_avg_rigor():
    rows = [
        dsr(visits=1, calls=5, followups=10, new_leads=2, proposals=1),  # full score
        dsr(visits=0, calls=0, followups=0, new_leads=0, proposals=0),   # zero score
    ]
    agg = aggregate_rigor_breakdown(rows)
    assert agg["avg_rigor"] == calculate_avg_rigor(rows)


def test_aggregate_breakdown_identifies_weakest_component():
    # Strong on everything except follow-ups across both days.
    rows = [
        dsr(visits=1, calls=5, followups=0, new_leads=2, proposals=1),
        dsr(visits=1, calls=5, followups=0, new_leads=2, proposals=1),
    ]
    agg = aggregate_rigor_breakdown(rows)
    assert agg["weakest"]["key"] == "followups"
    assert agg["weakest"]["earned_pct"] == 0.0
    assert agg["components"]["visits"]["earned_pct"] == 100.0


def test_aggregate_breakdown_excludes_exempt_wfh_presales_from_component_split():
    rows = [
        dsr(visits=1, calls=5, followups=10, new_leads=2, proposals=1),
        dsr(status="leave"),
        dsr(status="wfh", calls=50),  # would skew calls% if wrongly included
    ]
    agg = aggregate_rigor_breakdown(rows)
    assert agg["days_counted"] == 1
    assert agg["components"]["calls"]["earned_pct"] == 100.0


def test_aggregate_breakdown_empty_list_is_safe():
    agg = aggregate_rigor_breakdown([])
    assert agg["avg_rigor"] == 0.0
    assert agg["weakest"] is None
    assert agg["days_counted"] == 0
