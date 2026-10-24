"""Company-performance FGA parameter design, added 2026-10-24 (Amit: up to 5
scoring parameters per role template — 3 self-performance + up to 1
company-performance, one slot held in reserve). Pure-logic tests only, same
boundary as the rest of this suite (test_crm_admin_role.py etc.) — no
route-handler-level DB/HTTP integration tests exist for scoring.py today,
and this doesn't add that boundary just for these two endpoints.
"""
from app.routers.scoring import ParameterIn, MAX_ACTIVE_PARAMETERS, _validate_weights, _can_enter_company_kpi
from app.services import scoring_engine
from app.models import User
from fastapi import HTTPException
import pytest


def _param(name="P", weight=20.0, active=True, bonus=False, source="activity.rigor_avg"):
    return ParameterIn(name=name, weight_pct=weight, metric_source=source,
                        calc_type="pct", is_active=active, is_bonus=bonus)


def test_max_active_parameters_is_five():
    # Amit's explicit design cap, 2026-10-24 — change this constant
    # deliberately, not by accident, if the business rule ever changes.
    assert MAX_ACTIVE_PARAMETERS == 5


def test_validate_weights_allows_exactly_five_active_summing_to_100():
    params = [_param(f"P{i}", weight=20.0) for i in range(5)]
    _validate_weights(params)  # should not raise


def test_validate_weights_rejects_six_active_parameters():
    params = [_param(f"P{i}", weight=100 / 6) for i in range(6)]
    with pytest.raises(HTTPException) as exc:
        _validate_weights(params)
    assert exc.value.status_code == 400
    assert "At most 5 active parameters" in exc.value.detail


def test_validate_weights_disabled_parameters_dont_count_toward_cap():
    # 5 active (summing to 100) + 2 disabled (any weight) — a disabled
    # parameter is parked, not deleted, and must never block the save.
    params = [_param(f"P{i}", weight=20.0) for i in range(5)] + \
        [_param("Disabled A", weight=30.0, active=False), _param("Disabled B", weight=30.0, active=False)]
    _validate_weights(params)  # should not raise


def test_validate_weights_bonus_lines_excluded_from_cap():
    # Bonus lines sit outside the 100%-weighted split (0033) and must also
    # sit outside the 5-parameter cap — they're not one of the "3 self + 1
    # company" slots Amit is capping.
    params = [_param(f"P{i}", weight=20.0) for i in range(5)] + \
        [_param("Bonus", weight=5.0, bonus=True)]
    _validate_weights(params)  # should not raise


def test_validate_weights_still_enforces_sum_to_100():
    params = [_param("Only", weight=50.0)]
    with pytest.raises(HTTPException) as exc:
        _validate_weights(params)
    assert "sum to 100" in exc.value.detail


@pytest.mark.parametrize("role,org_role_key,expected", [
    ("finance", None, True),            # Amit's explicit call: Finance owns this number
    ("business_head", None, True),      # manager-tier+ (role_level >= 25)
    ("regional_manager", None, True),
    ("rep", None, False),
    ("inside_sales", None, False),
    ("hr", None, False),                # hr sees the FGA nav section but is not Finance
    ("rep", "super_admin", True),       # explicit admin org_role_key overrides level
])
def test_can_enter_company_kpi(role, org_role_key, expected):
    u = User(role=role, org_role_key=org_role_key)
    assert _can_enter_company_kpi(u) is expected


def test_company_manual_metrics_registry_has_revenue_target():
    assert "company_manual.revenue_target_achievement_pct" in scoring_engine.COMPANY_MANUAL_METRICS


def test_company_manual_metrics_are_disjoint_from_individual_registry():
    # company_manual.* must never collide with a METRIC_REGISTRY key or a
    # "manual." key — compute_score's dispatch relies on the prefix alone to
    # route correctly, so an overlapping key would silently pick the wrong
    # branch.
    individual_keys = set(scoring_engine.METRIC_REGISTRY.keys())
    assert individual_keys.isdisjoint(scoring_engine.COMPANY_MANUAL_METRICS)
    assert all(k.startswith("company_manual.") for k in scoring_engine.COMPANY_MANUAL_METRICS)
