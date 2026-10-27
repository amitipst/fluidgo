"""v1.6.1 - one definition of open / amount / win % across Deals, Health and the radar."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS
import uuid

import pytest

from app.services import deal_rules_service as r
from app.services import weak_area_service as wa

RULES = {"stages": {k: dict(v) for k, v in r.DEFAULT_STAGE_RULES.items()},
         "convert_min_stage": "sp4_qualification_bant", "deal_start_stage": "sp5_scope_proposal",
         "new_deal_min_stage": "sp5_scope_proposal"}
NOW = datetime(2026, 10, 27, 7, tzinfo=timezone.utc)
TODAY = date(2026, 10, 27)
U1 = uuid.uuid4()


def deal(**kw):
    base = dict(id=uuid.uuid4(), user_id=U1, company="Acme", title=None, stage="hot", sp_stage="sp5_scope_proposal",
                deal_value=None, win_probability=None, ai_closure_pct=None, last_activity_at=NOW - timedelta(days=1),
                created_at=NOW - timedelta(days=30), closure_eta=TODAY + timedelta(days=30), next_step="call",
                recurring_revenue=500000, one_time_revenue=500000, presales_owner_id=uuid.uuid4(), decision_maker="CIO",
                contact_id=uuid.uuid4(), reengage_at=None, reengage_done=False, archived=False, invoiced_at=None,
                won_at=None, won_ref=None, won_basis=None, account_id=uuid.uuid4())
    base.update(kw)
    return NS(**base)


def report(deals):
    return wa.build_report(list(deals), [], RULES, TODAY, NOW, U1, {U1: "Rep One"})


@pytest.mark.parametrize("stage,expected", [("cold", True), ("hot", True), ("qualification", True),
                                            ("closed_won", False), ("closed_lost", False),
                                            ("dropped", False), ("on_hold", False)])
def test_is_open_one_definition(stage, expected):
    assert r.is_open(deal(stage=stage)) is expected


def test_archived_is_not_open():
    assert r.is_open(deal(archived=True)) is False


def test_amount_uses_arr_plus_one_time_then_legacy_value():
    assert r.deal_amount(deal(recurring_revenue=300, one_time_revenue=200)) == 500
    assert r.deal_amount(deal(recurring_revenue=None, one_time_revenue=None, deal_value=700)) == 700
    assert r.deal_amount(deal(recurring_revenue=None, one_time_revenue=None, deal_value=None)) == 0


def test_metrics_never_guess_a_missing_win_pct():
    legacy = deal(sp_stage=None, stage="qualification", recurring_revenue=None, one_time_revenue=None, deal_value=2_000_000)
    m = r.deal_metrics(legacy, RULES)
    assert m["win_pct"] is None and m["weighted_amount"] is None and m["amount"] == 2_000_000 and m["is_open"]


def test_metrics_weight_by_stage_default():
    m = r.deal_metrics(deal(sp_stage="sp5_scope_proposal"), RULES)   # 45% default
    assert m["win_pct"] == 45 and m["weighted_amount"] == 450_000


def test_radar_counts_unweighted_deals_separately():
    rep = report([deal(), deal(sp_stage=None, stage="qualification")])
    s = rep["summary"]
    assert s["open_count"] == 2 and s["unweighted_count"] == 1
    assert s["weighted_value"] == 450_000      # only the deal with a win % is weighted


def test_radar_open_excludes_on_hold_and_dropped():
    rep = report([deal(), deal(stage="on_hold"), deal(stage="dropped")])
    assert rep["summary"]["open_count"] == 1


def test_one_valued_deal_is_a_data_gap_not_concentration():
    big = deal(recurring_revenue=1_000_000, one_time_revenue=1_000_000, win_probability=50)
    blanks = [deal(sp_stage=None, stage="qualification", recurring_revenue=None, one_time_revenue=None) for _ in range(4)]
    rep = report([big, *blanks])
    keys = {f["key"] for f in rep["findings"]}
    assert "concentration" not in keys and "no_split" in keys


def test_legacy_deals_flagged_as_off_the_ladder():
    rep = report([deal(sp_stage=None, stage="qualification")])
    f = next(x for x in rep["findings"] if x["key"] == "no_sp_stage")
    assert f["count"] == 1


def test_headlines_read_cleanly_in_lakh_crore():
    d = deal(closure_eta=TODAY - timedelta(days=2), recurring_revenue=5_000_000, one_time_revenue=5_000_000)
    h = report([d])["headlines"]
    assert h and not any(" - " in x for x in h)
    assert any("₹1.00 Cr" in x for x in h)


def test_lead_accepts_requirement_detail():
    from app.routers.leads import LeadIn
    m = LeadIn(date=date(2026, 10, 27), requirement="Other", requirement_detail="VDI instead of new workstations")
    assert m.requirement_detail == "VDI instead of new workstations"


def test_migration_0042_follows_0041():
    import pathlib
    import re
    path = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0042_lead_requirement_detail.py"
    text = path.read_text()
    assert re.search(r'^revision = "0042"', text, re.M) and re.search(r'^down_revision = "0041"', text, re.M)


# ── order-booking date (won_at) for revenue / FGA / incentives ───────────────
def test_won_date_prefers_order_booking_date_then_old_closure_date():
    from app.services.booking_date import won_date_of
    d_new = deal(won_at=date(2026, 11, 2), closure_eta=date(2026, 10, 31))
    d_old = deal(won_at=None, closure_eta=date(2026, 9, 15))
    assert won_date_of(d_new) == date(2026, 11, 2)       # actual booking wins over the old forecast date
    assert won_date_of(d_old) == date(2026, 9, 15)       # legacy deal: history does not move


def test_won_date_sql_is_a_coalesce_of_won_at_then_closure_eta():
    from app.services.booking_date import won_date_col
    sql = str(won_date_col())
    assert "coalesce" in sql.lower() and "won_at" in sql and "closure_eta" in sql
