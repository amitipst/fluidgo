import asyncio
from types import SimpleNamespace as NS
from app.services import dsr_routing_service as r


def test_notify_rules():
    assert r.should_notify(False, None)
    assert r.should_notify(True, "rejected")
    assert not r.should_notify(True, "submitted")
    assert not r.should_notify(True, "approved")


def test_notice_text_and_escaping():
    s, h, t = r.build_notice("A <b>Rep", "2026-10-27", 62, False)
    assert "submitted" in s and "2026-10-27" in s
    assert "<b>Rep" not in h and "&lt;b&gt;Rep" in h
    s2, _, _ = r.build_notice("A", "2026-10-27", 62, True)
    assert "resubmitted" in s2


def test_defaults_keep_business_head_off():
    assert r.DEFAULTS == {"notify_manager": True, "cc_business_head": False}
