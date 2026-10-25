"""Leads SPANCO stage ladder + feature-flag config fallback (migration 0038,
2026-10-24). Pure-logic tests only, same boundary as test_company_kpi.py —
the get_feature_flag/get_lead_stages async helpers that actually touch the
DB are exercised indirectly through is_valid_stage_key/default_stage_for_status
and the DEFAULT_LEAD_STAGES constant itself, mirroring how this suite tests
scoring_engine constants without a live Postgres.
"""
from app.services import lead_stage_service as svc


def test_default_stages_has_eleven_stages_in_kylas_order():
    # Amit's exact Kylas screenshot order, 2026-10-24: SP1..SP7 then
    # Hold / Won / Closed Unqualified / Closed Lost.
    keys = [s["key"] for s in sorted(svc.DEFAULT_LEAD_STAGES, key=lambda s: s["sort_order"])]
    assert keys == [
        "sp1_identifying", "sp2_profiling_bant", "sp3_understanding",
        "sp4_qualification_bant", "sp5_scope_proposal", "sp6_techno_commercial",
        "sp7_negotiation", "hold", "won", "closed_unqualified", "closed_lost",
    ]


def test_default_stages_sort_orders_are_unique_and_sequential():
    orders = sorted(s["sort_order"] for s in svc.DEFAULT_LEAD_STAGES)
    assert orders == list(range(1, len(svc.DEFAULT_LEAD_STAGES) + 1))


def test_exactly_three_terminal_stages_matching_kylas_closed_states():
    terminal = {s["key"] for s in svc.DEFAULT_LEAD_STAGES if s["is_terminal"]}
    assert terminal == {"won", "closed_unqualified", "closed_lost"}


def test_hold_is_not_terminal():
    # Hold is a pause, not a close — Kylas keeps it as its own column
    # distinct from the three Closed states, and so do we.
    hold = next(s for s in svc.DEFAULT_LEAD_STAGES if s["key"] == "hold")
    assert hold["is_terminal"] is False
    assert hold["outcome"] is None


def test_won_outcome_is_won_and_closed_states_are_lost():
    by_key = {s["key"]: s for s in svc.DEFAULT_LEAD_STAGES}
    assert by_key["won"]["outcome"] == "won"
    assert by_key["closed_unqualified"]["outcome"] == "lost"
    assert by_key["closed_lost"]["outcome"] == "lost"


def test_every_stage_has_a_color_for_the_kanban_dot():
    assert all(s.get("color") for s in svc.DEFAULT_LEAD_STAGES)


def test_is_valid_stage_key_accepts_known_key():
    assert svc.is_valid_stage_key("sp3_understanding", svc.DEFAULT_LEAD_STAGES) is True


def test_is_valid_stage_key_rejects_unknown_key():
    # Guards the PATCH /leads/{id}/stage 422 path against a typo or a stale
    # frontend sending a key from a previous feature_flags config.
    assert svc.is_valid_stage_key("not_a_real_stage", svc.DEFAULT_LEAD_STAGES) is False


def test_is_valid_stage_key_against_empty_list_is_always_false():
    assert svc.is_valid_stage_key("sp1_identifying", []) is False


def test_default_stage_for_status_maps_known_lead_statuses():
    assert svc.default_stage_for_status("new") == "sp1_identifying"
    assert svc.default_stage_for_status("qualified") == "sp3_understanding"
    assert svc.default_stage_for_status("proposal") == "sp5_scope_proposal"
    assert svc.default_stage_for_status("closed_won") == "won"
    assert svc.default_stage_for_status("closed_lost") == "closed_lost"


def test_default_stage_for_status_converted_lands_on_won():
    # A converted lead already did its job by becoming a pipeline deal —
    # see the docstring for why that maps to 'won' rather than leaving it
    # stranded mid-ladder.
    assert svc.default_stage_for_status("converted") == "won"


def test_default_stage_for_status_unknown_falls_back_to_first_stage():
    assert svc.default_stage_for_status("some_future_status") == "sp1_identifying"


def test_default_stage_for_status_never_returns_a_key_outside_the_ladder():
    valid_keys = {s["key"] for s in svc.DEFAULT_LEAD_STAGES}
    for status in ["new", "qualified", "proposal", "closed_won", "closed_lost",
                   "converted", "unknown_status"]:
        assert svc.default_stage_for_status(status) in valid_keys
