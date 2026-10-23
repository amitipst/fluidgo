"""Regression tests for the 2026-10-23 revenue-undercounting bug (Amit, overnight
session): every revenue sum across analytics.py, scoring_engine.py, incentives.py
and pipeline.py read PipelineDeal.deal_value only, so any deal entered via
Pipeline Sheet by rep's (v1.4.1) ARR/One-time fields instead of the legacy
single field was silently counted as ₹0 — in Revenue Intelligence, in the FGA
"Business Generation" metric (40% weight, compensation-linked), in incentive
scheme qualification, and in the Opportunities Win-Loss widget.

The fix routes every one of those call sites through pipeline_sheet_service's
already-unit-tested amounts() helper (see test_pipeline_sheet_service.py's
test_amounts_fallback_to_deal_value_for_old_deals) instead of a parallel
re-implementation, specifically so this can't drift out of sync with what
Pipeline Sheet / Opportunities already display for the same deal.

These tests exercise analytics.py's _deal_revenue() wrapper directly with
fake deal objects (SimpleNamespace, same pattern as
test_pipeline_sheet_service.py) — no DB needed, matching this suite's
existing pure-function convention (see conftest.py)."""
from types import SimpleNamespace as NS
from app.routers.analytics import _deal_revenue


def deal(**kw):
    base = dict(recurring_revenue=None, one_time_revenue=None, deal_value=None)
    base.update(kw)
    return NS(**base)


def test_deal_revenue_falls_back_to_deal_value_for_pre_v1_4_1_deals():
    # The exact shape of every deal before Pipeline Sheet existed — this MUST
    # keep working identically to the old `float(d.deal_value or 0)` code.
    assert _deal_revenue(deal(deal_value=500000)) == 500000.0


def test_deal_revenue_zero_when_nothing_set():
    assert _deal_revenue(deal()) == 0.0


def test_deal_revenue_uses_arr_plus_one_time_when_either_is_set():
    # This is the exact bug: a deal entered via Pipeline Sheet's ARR/One-time
    # fields, with deal_value left blank, used to sum as ₹0 everywhere in
    # Revenue Intelligence / FGA / incentives / win-loss. Must now be the sum.
    assert _deal_revenue(deal(recurring_revenue=660000, one_time_revenue=3500000)) == 4160000.0


def test_deal_revenue_one_time_only_still_counts_as_the_new_path():
    # recurring_revenue is None but one_time_revenue is set — NOT the
    # "nothing set" case, so deal_value must NOT be used as a fallback here
    # even if it happens to be populated too (ARR/One-time wins once either is set).
    assert _deal_revenue(deal(one_time_revenue=800000, deal_value=1)) == 800000.0


def test_deal_revenue_arr_only_still_counts_as_the_new_path():
    assert _deal_revenue(deal(recurring_revenue=1200000, deal_value=1)) == 1200000.0
