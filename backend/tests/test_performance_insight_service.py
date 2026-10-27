from datetime import date

from app.services import performance_insight_service as pis

TODAY = date(2026, 10, 27)


def rigor(avg=30.0, weakest=("followups", "Follow-ups", 12.0), days=10):
    return {"avg_rigor": avg, "days_counted": days,
            "weakest": {"key": weakest[0], "label": weakest[1], "earned_pct": weakest[2]}}


def report(*findings):
    return {"findings": [{"key": k, "count": c, "value": v, "items": [{"company": "Acme"}]} for k, c, v in findings]}


def keys(out):
    return [i["key"] for i in out["items"]]


def test_low_rigor_is_high_and_names_the_weakest_component_with_a_lever():
    out = pis.build_insights(rigor(30), TODAY, TODAY, None)
    assert out["items"][0]["key"] == "rigor" and out["items"][0]["severity"] == "high"
    w = next(i for i in out["items"] if i["key"] == "rigor_weakest")
    assert "Follow-ups" in w["title"] and "30 points" in w["action"]


def test_good_rigor_is_positive_and_adds_no_weakest_line():
    out = pis.build_insights(rigor(82), TODAY, TODAY, None)
    assert out["items"][0]["severity"] == "good" and "rigor_weakest" not in keys(out)
    assert out["headline"] == "You are on track"




def test_dsr_gap_severity_grows_with_days():
    assert not any(i["key"] == "dsr_gap" for i in pis.build_insights(None, date(2026, 10, 26), TODAY, None)["items"])
    mid = next(i for i in pis.build_insights(None, date(2026, 10, 24), TODAY, None)["items"] if i["key"] == "dsr_gap")
    high = next(i for i in pis.build_insights(None, date(2026, 10, 20), TODAY, None)["items"] if i["key"] == "dsr_gap")
    assert mid["severity"] == "medium" and high["severity"] == "high"


def test_deal_findings_become_actions_ranked_by_severity():
    out = pis.build_insights(rigor(80), TODAY, TODAY, report(("no_split", 4, 0), ("past_eta", 2, 500000)))
    ks = keys(out)
    assert ks.index("past_eta") < ks.index("no_split")
    assert "2 of your deals are past their expected closure date" in [i["title"] for i in out["items"]]


def test_unknown_findings_are_ignored_and_empty_input_does_not_crash():
    out = pis.build_insights(None, None, TODAY, report(("something_else", 1, 0)))
    assert out["items"] and all(i["key"] != "something_else" for i in out["items"])


def test_all_clear_when_nothing_to_do():
    out = pis.build_insights(rigor(90), TODAY, TODAY, report())
    assert "all_clear" in keys(out) and out["basis"].endswith("No AI model is called.")


def test_items_are_capped():
    r = report(*[(k, 1, 0) for k in pis.DEAL_RULES])
    assert len(pis.build_insights(rigor(20), date(2026, 10, 1), TODAY, r)["items"]) <= 6
