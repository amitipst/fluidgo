"""Tests for the Executive Intelligence Digest (added 2026-10-24, R2 of
fluidgo-services-intelligence-platform-assessment.md — Rambo Commander's
answer to Amit's "benchmark each feature against sales cadence, sales
intelligence and business revenue" instruction, built per his "develop the
same and wait for me to commit").

Pure-function tests only, same SimpleNamespace-fake-row convention as
test_rigor_breakdown.py / test_analytics_revenue_fix.py — no DB needed.
build_digest() itself is a thin DB-aggregation wrapper around already-tested
primitives (pipeline_sheet_service.amounts, rigor_service, compliance_service,
permission_service) and isn't re-tested here, matching this suite's existing
convention of testing the pure helpers around a DB-querying entry point
rather than the entry point itself (see aggregate_rigor_breakdown vs.
compute_compliance)."""
from types import SimpleNamespace as NS

from app.services.exec_digest_service import (
    _current_period, _deal_value, _serialize_deal, _inr, render_html, STALE_DEAL_DAYS,
)


def deal(**kw):
    base = dict(id="d1", company="Acme Corp", stage="proposal",
                recurring_revenue=None, one_time_revenue=None, deal_value=None,
                last_activity_at=None)
    base.update(kw)
    return NS(**base)


def test_deal_value_falls_back_to_deal_value_for_pre_v1_4_1_deals():
    assert _deal_value(deal(deal_value=250000)) == 250000.0


def test_deal_value_uses_arr_plus_one_time_when_set():
    assert _deal_value(deal(recurring_revenue=100000, one_time_revenue=50000)) == 150000.0


def test_deal_value_zero_when_nothing_set():
    assert _deal_value(deal()) == 0.0


def test_serialize_deal_shape_and_rounding():
    d = deal(deal_value=100000.456, stage="negotiation")
    s = _serialize_deal(d)
    assert s["id"] == "d1"
    assert s["company"] == "Acme Corp"
    assert s["stage"] == "negotiation"
    assert s["value"] == 100000.46
    assert s["last_activity_at"] is None


def test_current_period_format():
    p = _current_period()
    assert len(p) == 7 and p[4] == "-"


def test_inr_formats_with_thousands_separator():
    assert _inr(1234567) == "₹1,234,567"
    assert _inr(None) == "—"
    assert _inr(0) == "₹0"


def test_stale_deal_days_is_two_weeks():
    # Business rule from the assessment doc — matches the 14-day definition
    # already used elsewhere for "at risk" in Opportunities/Pipeline.
    assert STALE_DEAL_DAYS == 14


def _digest(**overrides):
    base = {
        "period": "2026-10", "generated_at": "2026-10-24T00:00:00+00:00",
        "revenue": {"achieved": 500000.0, "target": 1000000.0, "achievement_pct": 50.0},
        "pipeline": {
            "open_count": 2, "open_value": 300000.0, "weighted_forecast": 150000.0,
            "at_risk": [], "recent_wins": [],
        },
        "rigor": {"avg_rigor": 72.5, "weakest": {"key": "followups", "label": "Follow-ups"}},
        "compliance": {"avg_pct": 88.0, "at_risk_count": 0, "at_risk_reps": []},
    }
    base.update(overrides)
    return base


def test_render_html_handles_no_target_set_without_crashing():
    html = render_html(_digest(revenue={"achieved": 0.0, "target": None, "achievement_pct": None}),
                        "Amit")
    assert "no target set" in html
    assert "₹0" in html


def test_render_html_handles_empty_deal_lists():
    html = render_html(_digest(), "Amit")
    assert "None — pipeline is current." in html
    assert "No closed-won deals yet this period." in html


def test_render_html_lists_deals_when_present():
    html = render_html(_digest(pipeline={
        "open_count": 1, "open_value": 100000.0, "weighted_forecast": 50000.0,
        "at_risk": [{"id": "d1", "company": "Stale Co", "value": 100000.0}],
        "recent_wins": [{"id": "d2", "company": "Won Co", "value": 200000.0}],
    }), "Amit")
    assert "Stale Co" in html
    assert "Won Co" in html


def test_render_html_handles_no_weakest_rigor_component():
    html = render_html(_digest(rigor={"avg_rigor": None, "weakest": None}), "Amit")
    assert html  # renders without KeyError/TypeError
