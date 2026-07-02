"""Regression coverage for the existing v1 rule-based scorers — none of this had
tests before; adding them here since the v2 scoring_engine now depends on
calculate_rigor_score/bant_score staying correct."""
from types import SimpleNamespace
from app.services.rigor_service import calculate_rigor_score, bant_score, score_lead, rigor_label


def _dsr(**overrides):
    base = dict(status="working", visits=0, calls=0, followups=0, new_leads=0, proposals=0)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_rigor_score_caps_each_component():
    dsr = _dsr(visits=10, calls=20, followups=30, new_leads=10, proposals=10)
    # visits capped at 20, calls capped at 20, followups capped at 30, leads capped at 20, proposals capped at 10 -> 100
    assert calculate_rigor_score(dsr) == 100


def test_rigor_score_exempt_for_leave_and_holiday():
    assert calculate_rigor_score(_dsr(status="leave")) == -1
    assert calculate_rigor_score(_dsr(status="holiday")) == -1


def test_rigor_score_zero_activity():
    assert calculate_rigor_score(_dsr()) == 0


def _meeting(**overrides):
    base = dict(bant_budget=False, bant_authority=False, bant_need=False, bant_timeline=False, opportunity=False)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_bant_all_four_is_hot():
    m = _meeting(bant_budget=True, bant_authority=True, bant_need=True, bant_timeline=True)
    result = bant_score(m)
    assert result == {"bant_filled": 4, "closure_pct": 85, "intent": "hot", "gaps": []}


def test_bant_three_with_need_is_hot():
    m = _meeting(bant_budget=True, bant_authority=True, bant_need=True, bant_timeline=False)
    assert bant_score(m)["intent"] == "hot"
    assert bant_score(m)["gaps"] == ["Timeline"]


def test_bant_zero_filled_is_cold():
    m = _meeting()
    result = bant_score(m)
    assert result["intent"] == "cold"
    assert result["closure_pct"] == 5
    assert set(result["gaps"]) == {"Budget", "Authority", "Need", "Timeline"}


def test_bant_one_filled_with_opportunity_is_engaged():
    m = _meeting(bant_budget=True, opportunity=True)
    assert bant_score(m)["intent"] == "engaged"


def _lead(**overrides):
    base = dict(source="Call", requirement=None, next_action=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_lead_score_referral_highest_base():
    assert score_lead(_lead(source="Referral")) > score_lead(_lead(source="Email"))


def test_lead_score_bonuses_for_requirement_and_next_action():
    bare = score_lead(_lead(source="Call"))
    with_requirement = score_lead(_lead(source="Call", requirement="Needs a full MS licensing refresh"))
    with_both = score_lead(_lead(source="Call", requirement="Needs a full MS licensing refresh", next_action="Follow up Monday"))
    assert bare < with_requirement < with_both


def test_lead_score_capped_at_100():
    assert score_lead(_lead(source="Referral", requirement="x" * 50, next_action="call")) == 100


def test_rigor_label_bands():
    assert rigor_label(-1) == "exempt"
    assert rigor_label(90) == "excellent"
    assert rigor_label(75) == "good"
    assert rigor_label(55) == "average"
    assert rigor_label(10) == "needs_improvement"
