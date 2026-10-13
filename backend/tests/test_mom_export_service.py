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
