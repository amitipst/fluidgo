"""Deal rules (v1.5.0): ARR/One-time mandatory, SP-stage win %, SP7 floor of 70."""
import asyncio
from types import SimpleNamespace as NS

import pytest

from app.services import deal_rules_service as r

RULES = {"stages": {k: dict(v) for k, v in r.DEFAULT_STAGE_RULES.items()},
         "require_company_contact": True, "require_revenue_split": True}


def deal(**kw):
    base = dict(stage="warm", win_probability=None, sp_stage=None, ai_closure_pct=None,
                recurring_revenue=None, one_time_revenue=None)
    base.update(kw)
    return NS(**base)


# ── win probability ──────────────────────────────────────────────────────────
def test_negotiation_floor_is_70_and_is_amits_number():
    assert r.DEFAULT_STAGE_RULES["sp7_negotiation"]["floor"] == 70
    assert r.DEFAULT_STAGE_RULES["sp7_negotiation"]["default"] >= 70


def test_every_earlier_stage_has_no_floor_and_defaults_rise_with_the_ladder():
    order = ["sp1_identifying", "sp2_profiling_bant", "sp3_understanding", "sp4_qualification_bant",
             "sp5_scope_proposal", "sp6_techno_commercial", "sp7_negotiation"]
    defaults = [r.DEFAULT_STAGE_RULES[k]["default"] for k in order]
    assert defaults == sorted(defaults) and len(set(defaults)) == len(defaults)
    assert all(r.DEFAULT_STAGE_RULES[k]["floor"] == 0 for k in order[:-1])


def test_nothing_sent_uses_the_stage_default():
    assert r.resolve_win_probability("qualification", "sp3_understanding", None, RULES) == 20
    assert r.resolve_win_probability("hot", "sp7_negotiation", None, RULES) == 75


def test_negotiation_below_70_is_rejected_with_a_readable_message():
    with pytest.raises(r.RuleViolation) as e:
        r.resolve_win_probability("hot", "sp7_negotiation", 69, RULES)
    assert "70%" in str(e.value) and "Negotiation" in str(e.value)


def test_negotiation_at_or_above_70_is_kept():
    assert r.resolve_win_probability("hot", "sp7_negotiation", 70, RULES) == 70
    assert r.resolve_win_probability("hot", "sp7_negotiation", 95, RULES) == 95


def test_earlier_stages_let_the_rep_go_lower_or_higher_than_default():
    assert r.resolve_win_probability("warm", "sp3_understanding", 5, RULES) == 5
    assert r.resolve_win_probability("warm", "sp3_understanding", 90, RULES) == 90


def test_closed_states_override_whatever_was_sent():
    assert r.resolve_win_probability("closed_won", "sp7_negotiation", 10, RULES) == 100
    assert r.resolve_win_probability("closed_lost", "sp7_negotiation", 90, RULES) == 0
    assert r.resolve_win_probability("dropped", "sp2_profiling_bant", 40, RULES) == 0


def test_legacy_deal_without_sp_stage_is_untouched():
    assert r.resolve_win_probability("hot", None, 40, RULES) == 40
    assert r.resolve_win_probability("hot", None, None, RULES) is None


def test_unknown_sp_stage_behaves_like_no_sp_stage():
    assert r.resolve_win_probability("hot", "hold", 15, RULES) == 15


# ── revenue split ────────────────────────────────────────────────────────────
def test_both_arr_and_one_time_are_required_for_a_live_deal():
    with pytest.raises(r.RuleViolation):
        r.validate_revenue_split(None, None, "warm", RULES)
    with pytest.raises(r.RuleViolation):
        r.validate_revenue_split(100000, None, "warm", RULES)
    with pytest.raises(r.RuleViolation):
        r.validate_revenue_split(None, 50000, "warm", RULES)


def test_zero_is_a_valid_answer_but_not_zero_for_both():
    r.validate_revenue_split(0, 500000, "warm", RULES)      # licence sale, no ARR
    r.validate_revenue_split(1200000, 0, "warm", RULES)     # pure managed service
    with pytest.raises(r.RuleViolation):
        r.validate_revenue_split(0, 0, "warm", RULES)


def test_negative_amounts_rejected():
    with pytest.raises(r.RuleViolation):
        r.validate_revenue_split(-1, 500, "warm", RULES)


def test_won_deal_still_needs_the_split():
    with pytest.raises(r.RuleViolation):
        r.validate_revenue_split(None, None, "closed_won", RULES)


@pytest.mark.parametrize("stage", ["closed_lost", "dropped", "on_hold"])
def test_closing_or_parking_an_old_incomplete_deal_is_never_blocked(stage):
    r.validate_revenue_split(None, None, stage, RULES)


def test_rule_can_be_switched_off_by_config():
    off = {**RULES, "require_revenue_split": False}
    r.validate_revenue_split(None, None, "warm", off)


def test_deal_value_is_kept_in_sync_as_arr_plus_one_time():
    assert r.derive_deal_value(1200000, 300000) == 1500000
    assert r.derive_deal_value(0, 250000.5) == 250000.5
    assert r.derive_deal_value(None, None) is None


# ── one definition of the forecast probability ───────────────────────────────
def test_forecast_probability_order_rep_then_stage_then_ai():
    assert r.forecast_probability(deal(win_probability=55, sp_stage="sp7_negotiation", ai_closure_pct=10)) == 55
    assert r.forecast_probability(deal(sp_stage="sp7_negotiation", ai_closure_pct=10)) == 75
    assert r.forecast_probability(deal(sp_stage="sp2_profiling_bant")) == 10
    assert r.forecast_probability(deal(ai_closure_pct=33)) == 33
    assert r.forecast_probability(deal()) is None


def test_forecast_probability_closed_states():
    assert r.forecast_probability(deal(stage="closed_won", win_probability=20)) == 100
    assert r.forecast_probability(deal(stage="closed_lost", win_probability=90)) == 0
    assert r.forecast_probability(deal(stage="dropped")) == 0


def test_needs_revenue_split_flags_only_live_incomplete_deals():
    assert r.needs_revenue_split(deal()) is True
    assert r.needs_revenue_split(deal(recurring_revenue=0, one_time_revenue=5)) is False
    assert r.needs_revenue_split(deal(recurring_revenue=5)) is True
    assert r.needs_revenue_split(deal(stage="closed_lost")) is False
    assert r.needs_revenue_split(deal(stage="on_hold")) is False


# ── config override ──────────────────────────────────────────────────────────
def _with_flag(monkeypatch, flag):
    async def fake(_db, _key):
        return flag
    monkeypatch.setattr(r, "get_feature_flag", fake)


def test_get_rules_without_a_flag_row_returns_shipped_defaults(monkeypatch):
    _with_flag(monkeypatch, None)
    rules = asyncio.run(r.get_rules(None))
    assert rules["stages"]["sp7_negotiation"]["floor"] == 70
    assert rules["require_company_contact"] is True and rules["require_revenue_split"] is True


def test_get_rules_applies_a_config_override_without_a_deploy(monkeypatch):
    _with_flag(monkeypatch, NS(enabled=True, config={
        "stages": {"sp7_negotiation": {"floor": 80}, "sp1_identifying": {"default": 8}},
        "require_company_contact": False}))
    rules = asyncio.run(r.get_rules(None))
    assert {k: rules["stages"]["sp7_negotiation"][k] for k in ("default", "floor")} == {"default": 75, "floor": 80}
    assert rules["stages"]["sp1_identifying"]["default"] == 8
    assert rules["require_company_contact"] is False
    assert rules["require_revenue_split"] is True


def test_a_disabled_flag_row_is_ignored(monkeypatch):
    _with_flag(monkeypatch, NS(enabled=False, config={"stages": {"sp7_negotiation": {"floor": 10}}}))
    assert asyncio.run(r.get_rules(None))["stages"]["sp7_negotiation"]["floor"] == 70


# ── ladder through Won, and what "won" means (Amit, 2026-10-26) ──────────────
def test_ladder_runs_sp1_to_sp7_then_won():
    assert list(r.DEFAULT_STAGE_RULES) == ["sp1_identifying", "sp2_profiling_bant", "sp3_understanding",
        "sp4_qualification_bant", "sp5_scope_proposal", "sp6_techno_commercial", "sp7_negotiation", "won"]
    assert {k: r.DEFAULT_STAGE_RULES["won"][k] for k in ("default", "floor")} == {"default": 100, "floor": 100}
    assert [r.DEFAULT_STAGE_RULES[k]["default"] for k in list(r.DEFAULT_STAGE_RULES)[:7]] == [5, 10, 20, 30, 45, 60, 75]


def test_won_needs_customer_evidence_and_a_date():
    from datetime import date
    for basis in ("email", "loi", "po", "agreement"):
        r.validate_won(basis, date(2026, 10, 26))
    with pytest.raises(r.RuleViolation):
        r.validate_won(None, date(2026, 10, 26))
    with pytest.raises(r.RuleViolation):
        r.validate_won("verbal", date(2026, 10, 26))
    with pytest.raises(r.RuleViolation):
        r.validate_won("po", None)


def test_won_label():
    assert r.sp_stage_label("won") == "Won"
