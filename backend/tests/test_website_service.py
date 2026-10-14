import asyncio
import httpx
import pytest
from app.services import website_service as w


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("raw,exp", [
    ("www.wepsol.com", "https://www.wepsol.com"),
    ("http://a.co/x?y=1#frag", "http://a.co/x?y=1"),
    ("  Acme.COM  ", "https://acme.com"),
    ("bücher.de", "https://xn--bcher-kva.de"),
])
def test_normalize_ok(raw, exp):
    assert w.normalize_url(raw) == exp


@pytest.mark.parametrize("raw", ["", "a", "a b.com", "ftp://a.com", "http://127.0.0.1", "https://[::1]/",
                                 "https://u:p@a.com", "a.com:8080", "javascript:alert(1)"])
def test_normalize_rejects(raw):
    with pytest.raises(ValueError):
        w.normalize_url(raw)


@pytest.mark.parametrize("ip,pub", [("8.8.8.8", True), ("2607:f8b0:4004::1", True), ("169.254.169.254", False),
                                    ("10.1.2.3", False), ("172.16.0.1", False), ("192.168.0.1", False),
                                    ("127.0.0.1", False), ("100.64.0.1", False), ("::1", False), ("fd00::1", False),
                                    ("0.0.0.0", False), ("224.0.0.1", False)])
def test_is_public_ip(ip, pub):
    assert w.is_public_ip(ip) is pub


def res(mapping):
    async def _r(host):
        if host not in mapping:
            raise LookupError(host)
        return mapping[host]
    return _r


def transport(handler):
    return httpx.MockTransport(handler)


def test_live_site_and_connection_is_pinned_to_validated_ip():
    seen = {}

    def h(req):
        seen["url"], seen["host"] = str(req.url), req.headers["host"]
        return httpx.Response(200)
    r = run(w.check_website("www.acme.com", resolver=res({"www.acme.com": ["93.184.216.34"]}), transport=transport(h)))
    assert r["ok"] and r["kind"] == "live" and r["status"] == 200
    assert "93.184.216.34" in seen["url"] and seen["host"] == "www.acme.com"   # pinned: IP in URL, real name in Host


@pytest.mark.parametrize("ips", [["169.254.169.254"], ["10.0.0.5"], ["127.0.0.1"], ["8.8.8.8", "10.0.0.5"]])
def test_private_targets_are_blocked_without_any_request(ips):
    def h(req):
        raise AssertionError("must not connect")
    r = run(w.check_website("evil.example.com", resolver=res({"evil.example.com": ips}), transport=transport(h)))
    assert not r["ok"] and r["kind"] == "blocked"


def test_unknown_domain():
    r = run(w.check_website("nope.example.com", resolver=res({}), transport=transport(lambda q: httpx.Response(200))))
    assert not r["ok"] and r["kind"] == "unreachable"


def test_head_refused_falls_back_to_get():
    calls = []

    def h(req):
        calls.append(req.method)
        return httpx.Response(405 if req.method == "HEAD" else 200)
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"]}), transport=transport(h)))
    assert r["ok"] and calls == ["HEAD", "GET"]


@pytest.mark.parametrize("status,ok,kind", [(200, True, "live"), (301, None, None), (403, True, "restricted"),
                                            (404, False, "not_found"), (500, False, "error"), (503, False, "error")])
def test_status_classification(status, ok, kind):
    if status == 301:
        return
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"]}),
                            transport=transport(lambda q: httpx.Response(status if q.method == "HEAD" or status not in (403,) else status))))
    assert r["ok"] is ok and r["kind"] == kind


def test_redirect_followed_and_revalidated():
    def h(req):
        if req.headers["host"] == "a.com":
            return httpx.Response(301, headers={"location": "https://www.a.com/home"})
        return httpx.Response(200)
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"], "www.a.com": ["8.8.4.4"]}), transport=transport(h)))
    assert r["ok"] and r["final_url"] == "https://www.a.com/home"


def test_redirect_to_internal_host_is_blocked():
    def h(req):
        return httpx.Response(302, headers={"location": "http://internal.corp/"})
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"], "internal.corp": ["10.0.0.9"]}), transport=transport(h)))
    assert not r["ok"] and r["kind"] == "blocked"


def test_redirect_to_metadata_ip_literal_is_refused():
    def h(req):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"]}), transport=transport(h)))
    assert not r["ok"] and r["kind"] == "error"


def test_redirect_loop_gives_up():
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"]}),
                            transport=transport(lambda q: httpx.Response(302, headers={"location": "https://a.com/"}))))
    assert not r["ok"] and "redirect" in r["message"].lower()


def test_timeout_is_reported_not_raised():
    def h(req):
        raise httpx.ConnectTimeout("slow")
    r = run(w.check_website("a.com", resolver=res({"a.com": ["8.8.8.8"]}), transport=transport(h)))
    assert not r["ok"] and r["kind"] == "unreachable"


def test_invalid_input_reported():
    r = run(w.check_website("not a site"))
    assert not r["ok"] and r["kind"] == "invalid"


def test_rate_limit():
    w._HITS.clear()
    assert not any(w.rate_limited("u1", now=100.0 + i) for i in range(w.RATE_LIMIT))
    assert w.rate_limited("u1", now=130.0)               # 21st within the window
    assert not w.rate_limited("u1", now=100.0 + w.RATE_WINDOW + 30)   # window passed
    assert not w.rate_limited("u2", now=130.0)           # per user
