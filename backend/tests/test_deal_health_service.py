from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.services.deal_health_service import calculate_deal_health, deal_health_label


def _deal(**overrides):
    base = dict(ai_closure_pct=None, last_activity_at=None, roadblock=False,
                risk_level=None, budget_status=None, timeline_status=None, decision_maker=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_healthy_deal_no_negative_signals():
    deal = _deal(ai_closure_pct=85, last_activity_at=datetime.now(timezone.utc),
                 risk_level="low", budget_status="confirmed", timeline_status="on_track",
                 decision_maker="Jane Doe")
    score = calculate_deal_health(deal)
    assert score == 85
    assert deal_health_label(score) == "healthy"


def test_no_closure_pct_defaults_to_neutral_baseline():
    deal = _deal(last_activity_at=datetime.now(timezone.utc), decision_maker="Someone")
    assert calculate_deal_health(deal) == 50


def test_stale_activity_penalised():
    fresh = _deal(ai_closure_pct=80, last_activity_at=datetime.now(timezone.utc))
    stale_14d = _deal(ai_closure_pct=80, last_activity_at=datetime.now(timezone.utc) - timedelta(days=20))
    stale_30d = _deal(ai_closure_pct=80, last_activity_at=datetime.now(timezone.utc) - timedelta(days=45))
    assert calculate_deal_health(fresh) > calculate_deal_health(stale_14d) > calculate_deal_health(stale_30d)


def test_no_activity_ever_logged_penalised():
    never = _deal(ai_closure_pct=80, last_activity_at=None, decision_maker="Someone")
    assert calculate_deal_health(never) == 80 - 15


def test_roadblock_and_risk_and_budget_and_timeline_stack():
    deal = _deal(ai_closure_pct=80, last_activity_at=datetime.now(timezone.utc),
                 roadblock=True, risk_level="high", budget_status="unconfirmed",
                 timeline_status="delayed", decision_maker=None)
    # 80 - 15 (roadblock) - 15 (high risk) - 10 (unconfirmed) - 10 (delayed) - 5 (no DM)
    assert calculate_deal_health(deal) == 25


def test_critical_risk_caps_lower_than_high():
    high = _deal(ai_closure_pct=80, last_activity_at=datetime.now(timezone.utc), risk_level="high")
    critical = _deal(ai_closure_pct=80, last_activity_at=datetime.now(timezone.utc), risk_level="critical")
    assert calculate_deal_health(critical) < calculate_deal_health(high)


def test_score_never_goes_below_zero_or_above_hundred():
    disaster = _deal(ai_closure_pct=5, last_activity_at=datetime.now(timezone.utc) - timedelta(days=60),
                     roadblock=True, risk_level="critical", budget_status="unconfirmed",
                     timeline_status="delayed", decision_maker=None)
    assert calculate_deal_health(disaster) == 0

    perfect = _deal(ai_closure_pct=100, last_activity_at=datetime.now(timezone.utc),
                    risk_level="low", budget_status="confirmed", timeline_status="on_track",
                    decision_maker="Someone")
    assert calculate_deal_health(perfect) == 100


def test_labels_match_score_bands():
    assert deal_health_label(80) == "healthy"
    assert deal_health_label(79) == "watch"
    assert deal_health_label(60) == "watch"
    assert deal_health_label(59) == "at_risk"
    assert deal_health_label(40) == "at_risk"
    assert deal_health_label(39) == "critical"
    assert deal_health_label(0) == "critical"
