from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS
import uuid

import pytest

from app.services import deal_rules_service as r
from app.services import deal_duplicate_service as dup
from app.services import finance_notify_service as fin
from app.services import weak_area_service as wa

RULES = {"stages": {k: dict(v) for k, v in r.DEFAULT_STAGE_RULES.items()},
         "convert_min_stage": "sp4_qualification_bant", "deal_start_stage": "sp5_scope_proposal",
         "new_deal_min_stage": "sp5_scope_proposal"}
NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
TODAY = date(2026, 10, 26)
U1, U2 = uuid.uuid4(), uuid.uuid4()


def deal(**kw):
    base = dict(id=uuid.uuid4(), user_id=U1, company="Acme", title=None, stage="hot", sp_stage="sp5_scope_proposal",
                deal_value=1_000_000, win_probability=None, ai_closure_pct=None, last_activity_at=NOW - timedelta(days=1),
                created_at=NOW - timedelta(days=30), closure_eta=TODAY + timedelta(days=30), next_step="call",
                recurring_revenue=500000, one_time_revenue=500000, presales_owner_id=uuid.uuid4(), decision_maker="CIO",
                contact_id=uuid.uuid4(), reengage_at=None, reengage_done=False, archived=False, invoiced_at=None,
                won_at=None, won_ref=None, won_basis=None, account_id=uuid.uuid4())
    base.update(kw)
    return NS(**base)


def lead(**kw):
    base = dict(id=uuid.uuid4(), user_id=U1, company="Acme", requirement="SOC", stage="sp1_identifying", status="new",
                date=TODAY - timedelta(days=2), converted_to_deal_id=None, contact_id=None, account_id=None)
    base.update(kw)
    return NS(**base)


# ── conversion gate ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("stage", ["sp1_identifying", "sp2_profiling_bant", "sp3_understanding", None])
def test_convert_blocked_before_sp4(stage):
    with pytest.raises(r.RuleViolation):
        r.validate_convert(stage, RULES)


@pytest.mark.parametrize("stage", ["sp4_qualification_bant", "sp5_scope_proposal", "sp7_negotiation", "won"])
def test_convert_allowed_from_sp4(stage):
    r.validate_convert(stage, RULES)


@pytest.mark.parametrize("stage", ["hold", "closed_unqualified", "closed_lost"])
def test_convert_blocked_for_exit_stages(stage):
    with pytest.raises(r.RuleViolation):
        r.validate_convert(stage, RULES)


def test_stricter_gate_via_config():
    strict = {**RULES, "convert_min_stage": "sp5_scope_proposal"}
    with pytest.raises(r.RuleViolation):
        r.validate_convert("sp4_qualification_bant", strict)
    r.validate_convert("sp5_scope_proposal", strict)


def test_deal_start_stage():
    assert r.deal_start_stage("sp4_qualification_bant", RULES) == "sp5_scope_proposal"
    assert r.deal_start_stage("sp6_techno_commercial", RULES) == "sp6_techno_commercial"
    assert r.deal_start_stage("won", RULES) == "sp7_negotiation"


def test_new_deal_min_stage():
    with pytest.raises(r.RuleViolation):
        r.validate_new_deal_stage("sp3_understanding", RULES)
    r.validate_new_deal_stage("sp5_scope_proposal", RULES)
    r.validate_new_deal_stage("sp7_negotiation", RULES)


def test_forecast_category():
    assert r.forecast_category(NS(stage="hot", sp_stage="sp5_scope_proposal"), RULES) == "pipeline"
    assert r.forecast_category(NS(stage="hot", sp_stage="sp6_techno_commercial"), RULES) == "best_case"
    assert r.forecast_category(NS(stage="hot", sp_stage="sp7_negotiation"), RULES) == "commit"
    assert r.forecast_category(NS(stage="closed_won", sp_stage="won"), RULES) == "closed"
    assert r.forecast_category(NS(stage="closed_lost", sp_stage=None), RULES) is None


# ── duplicate alert ──────────────────────────────────────────────────────────
def test_duplicates_lists_open_only_and_hides_money_outside_scope():
    cid = uuid.uuid4()
    mine, theirs = deal(user_id=U1, contact_id=cid), deal(user_id=U2, title="SOC")
    closed = deal(stage="closed_lost")
    out = dup.summarise([mine, theirs, closed], [lead(), lead(status="converted")], {U1}, cid, {U1: "A", U2: "B"})
    assert len(out["deals"]) == 2 and len(out["leads"]) == 1 and out["count"] == 3
    assert out["deals"][0]["same_contact"] is True
    other = [d for d in out["deals"] if d["owner"] == "B"][0]
    assert other["viewable"] is False and "deal_value" not in other


def test_duplicates_scope_all_sees_values():
    out = dup.summarise([deal()], [], None)
    assert out["deals"][0]["viewable"] and out["deals"][0]["deal_value"] == 1_000_000


# ── finance notice ───────────────────────────────────────────────────────────
def test_finance_notice_contents():
    d = deal(stage="closed_won", won_basis="po", won_ref="PO-77", won_at=TODAY, title="NOC")
    subject, html, text = fin.build_won_notice(d, "Rep One")
    assert "Acme" in subject and "NOC" in subject
    assert "PO-77" in text and "Purchase order" in text and "₹1,000,000" in text and "Rep One" in html


def test_finance_notice_escapes_html():
    d = deal(company="<script>x</script>", won_basis="email", won_at=TODAY)
    assert "<script>" not in fin.build_won_notice(d, "x")[1]


# ── weak-area radar ──────────────────────────────────────────────────────────
def report(deals, leads=(), me=U1):
    return wa.build_report(list(deals), list(leads), RULES, TODAY, NOW, me, {U1: "Rep One", U2: "Rep Two"})


def keys(rep):
    return {f["key"] for f in rep["findings"]}


def test_clean_pipeline_has_no_findings():
    rep = report([deal()])
    assert rep["findings"] == [] and rep["summary"]["open_count"] == 1


def test_flags_stalled_past_eta_no_next_step_no_split():
    d = deal(last_activity_at=NOW - timedelta(days=30), closure_eta=TODAY - timedelta(days=3), next_step="",
             recurring_revenue=None)
    assert {"stalled", "past_eta", "no_next_step", "no_split"} <= keys(report([d]))


def test_closed_deals_are_not_flagged():
    assert keys(report([deal(stage="closed_lost", next_step="", closure_eta=TODAY - timedelta(days=9))])) == set()


def test_presales_and_decision_maker_findings():
    d = deal(sp_stage="sp6_techno_commercial", presales_owner_id=None, decision_maker=None, contact_id=None)
    assert {"no_presales_owner", "no_decision_maker"} <= keys(report([d]))


def test_concentration_flagged():
    big, s1, s2 = deal(deal_value=9_000_000), deal(deal_value=100_000), deal(deal_value=100_000)
    assert "concentration" in keys(report([big, s1, s2]))
    assert "concentration" not in keys(report([big, s1]))   # too few deals to call it a pattern


def test_lead_findings():
    q = lead(stage="sp5_scope_proposal", date=TODAY - timedelta(days=10))
    s = lead(stage="sp2_profiling_bant", date=TODAY - timedelta(days=40))
    k = keys(report([], [q, s]))
    assert {"qualified_unconverted", "stale_leads"} <= k


def test_renewals_and_won_uninvoiced():
    ren = deal(stage="closed_won", sp_stage="won", reengage_at=TODAY + timedelta(days=20))
    won = deal(stage="closed_won", sp_stage="won", won_at=TODAY - timedelta(days=45))
    assert {"renewals", "won_uninvoiced"} <= keys(report([ren, won]))


def test_reps_my_actions_and_presales_queue():
    mine = deal(user_id=U1, next_step="", presales_owner_id=U2)
    theirs = deal(user_id=U2, closure_eta=TODAY - timedelta(days=1))
    rep = report([mine, theirs], me=U1)
    assert [a["id"] for a in rep["my_actions"]] == [str(mine.id)]
    assert rep["reps"][0]["attention"] >= 1
    rep2 = report([mine, theirs], me=U2)
    assert [p["id"] for p in rep2["presales_queue"]] == [str(mine.id)]


def test_findings_sorted_high_first_and_samples_capped():
    deals = [deal(closure_eta=TODAY - timedelta(days=1), deal_value=i * 1000) for i in range(1, 15)]
    rep = report(deals)
    assert rep["findings"][0]["severity"] == "high"
    assert rep["findings"][0]["count"] == 14 and len(rep["findings"][0]["items"]) == 8
    assert rep["findings"][0]["items"][0]["value"] == 14000


def test_summary_weighted_by_category():
    rep = report([deal(sp_stage="sp7_negotiation", deal_value=1000000)])
    assert rep["summary"]["by_category"]["commit"]["count"] == 1
    assert rep["summary"]["weighted_value"] == 750000.0
