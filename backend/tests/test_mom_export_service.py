"""MOM export presentation tests — format-neutral helpers plus a render smoke
test per format (including the empty-meeting case, which must never raise)."""
import pytest
from app.services import mom_export_service as s

MEETING = dict(
    company="Nido Home Finance Ltd", date="2026-05-18", meeting_purpose="sales_discovery", meeting_type="F2F",
    attendees=[{"side": "us", "name": "danish", "email": ""},
               {"side": "customer", "name": "Dinesh Rao", "email": "d@nido.example"}],
    discussion_points=[{"point": "NOC scope", "responsibility_side": "us", "responsibility_name": "danish",
                        "target_date": "2026-10-01", "status": "in_progress"}],
    ai_mom_summary="## Summary\nA **good** meeting.\n- one\n- two", mom_status="draft",
)


def test_fmt_date():
    assert s.fmt_date("2026-05-18") == "18 May 2026"
    assert s.fmt_date("") == ""
    assert s.fmt_date("not-a-date") == "not-a-date"


def test_tidy_name_only_touches_all_lowercase():
    assert s.tidy_name("danish") == "Danish"
    assert s.tidy_name("McDonald") == "McDonald"


def test_attendee_lines_omit_no_email_noise():
    assert s._attendee_lines(MEETING["attendees"][:1]) == ["Danish"]
    assert s._attendee_lines(MEETING["attendees"][1:]) == ["Dinesh Rao (d@nido.example)"]


def test_owner_and_status():
    p = MEETING["discussion_points"][0]
    assert s._owner(p) == "Danish (Us)"
    assert s._status(p) == "In Progress"


def test_md_blocks():
    assert s._md_blocks(MEETING["ai_mom_summary"]) == [("h", "Summary"), ("p", "A **good** meeting."), ("li", "one"), ("li", "two")]


@pytest.mark.parametrize("fmt,magic", [("pdf", b"%PDF"), ("docx", b"PK"), ("xlsx", b"PK")])
def test_every_format_renders(fmt, magic):
    fn = s.EXPORT_RENDERERS[fmt][0]
    assert fn(s.build_minutes_document(MEETING)).startswith(magic)


@pytest.mark.parametrize("fmt", ["pdf", "docx", "xlsx"])
def test_empty_meeting_renders(fmt):
    empty = {**MEETING, "ai_mom_summary": None, "attendees": [], "discussion_points": []}
    assert s.EXPORT_RENDERERS[fmt][0](s.build_minutes_document(empty))


def test_email_html_escapes_and_has_no_raw_markdown():
    m = {**MEETING, "company": "A <b>&</b> Co"}
    html, text = s.render_email_html(s.build_minutes_document(m))
    assert "<b>&</b> Co" not in html and "A &lt;b&gt;" in html
    assert "##" not in html and "##" not in text


# ── Sender identity for Send-to-Customer ─────────────────────────────────────
def test_sender_headers_default_is_via_relay_with_reply_to(monkeypatch):
    from app.services import email_service as es
    monkeypatch.setattr(es.settings, "SMTP_FROM", "fluidGo <fluidgo-noreply@wepsol.com>")
    frm, env, reply = es._sender_headers("Danish Sayyed", "danish@fluidpro.in", as_user=False)
    assert "Danish Sayyed via fluidGo" in frm and "fluidgo-noreply@wepsol.com" in frm
    assert env == "fluidgo-noreply@wepsol.com" and reply == "danish@fluidpro.in"


def test_sender_headers_as_user(monkeypatch):
    from app.services import email_service as es
    frm, env, reply = es._sender_headers("Danish Sayyed", "danish@fluidpro.in", as_user=True)
    assert frm == "Danish Sayyed <danish@fluidpro.in>" and env == reply == "danish@fluidpro.in"


def test_sender_headers_without_sender_uses_relay(monkeypatch):
    from app.services import email_service as es
    frm, env, reply = es._sender_headers(None, None, as_user=False)
    assert reply is None and env == "fluidgo-noreply@wepsol.com"


# ── AI failure must never become minutes ─────────────────────────────────────
def test_is_ai_error_detects_the_service_failure_string():
    from app.services import ai_service
    assert ai_service.is_ai_error("⚠️ AI analysis unavailable: boom\n\nEnsure Ollama is running")
    assert not ai_service.is_ai_error("## Summary\nAll good")
    assert not ai_service.is_ai_error(None)


def test_export_ignores_stored_ai_error_text():
    bad = {**MEETING, "ai_mom_summary": "⚠️ AI analysis unavailable: [Errno -3] Temporary failure in name resolution"}
    doc = s.build_minutes_document(bad)
    assert doc.ai_mom_summary is None
    html, text = s.render_email_html(doc)
    assert "unavailable" not in html and "unavailable" not in text
    assert s.EXPORT_RENDERERS["pdf"][0](doc).startswith(b"%PDF")
