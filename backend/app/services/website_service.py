"""Live website check for the company form (warn, never block).

Security: this makes the SERVER fetch a user-supplied URL, which is the classic
SSRF shape (on EC2 the prize is the instance-metadata endpoint 169.254.169.254).
Controls, all enforced here and covered by tests:
  * only http/https, only ports 80/443, no credentials in the URL, no IP literals
  * every hostname is resolved and EVERY resulting address must be globally
    routable (private, loopback, link-local, CGNAT, multicast, reserved => refused)
  * the connection is pinned to the validated IP (Host header + SNI carry the real
    name), so DNS can't change between check and connect (rebinding)
  * redirects are followed manually (max 4) and each hop is re-validated
  * short timeouts, HEAD first, body never read, nothing from the target is
    returned to the caller except a status classification
"""
import asyncio
import ipaddress
import socket
import time
from collections import defaultdict, deque
from typing import Awaitable, Callable, Optional
from urllib.parse import urlsplit, urlunsplit, urljoin

import httpx

MAX_REDIRECTS = 4
ALLOWED_PORTS = {None, 80, 443}
TIMEOUT = httpx.Timeout(6.0, connect=3.0)
USER_AGENT = "fluidGo-site-check/1.0 (+company website verification)"
RATE_LIMIT = 20          # checks
RATE_WINDOW = 60.0       # per seconds, per user (in-process; single backend instance)

_REDIRECTS = {301, 302, 303, 307, 308}
_HITS: dict = defaultdict(deque)


class Blocked(Exception):
    """Target resolves to a non-public address or uses a disallowed form."""


def rate_limited(user_key: str, now: Optional[float] = None) -> bool:
    now = time.monotonic() if now is None else now
    q = _HITS[user_key]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


def normalize_url(raw: str) -> str:
    """Tidy a typed website into a canonical http(s) URL; ValueError if unusable."""
    s = (raw or "").strip()
    if not s or " " in s:
        raise ValueError("Enter a website address like www.acme.com")
    if "://" not in s:
        s = "https://" + s
    p = urlsplit(s)
    if p.scheme.lower() not in ("http", "https"):
        raise ValueError("Website must start with http:// or https://")
    if p.username or p.password:
        raise ValueError("Remove the username/password from the address")
    host = p.hostname
    if not host or "." not in host:
        raise ValueError("Enter a website address like www.acme.com")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass                                   # not an IP literal — good
    else:
        raise ValueError("Use the company's website name, not an IP address")
    try:
        port = p.port
    except ValueError:
        raise ValueError("Website address has an invalid port")
    if port not in ALLOWED_PORTS:
        raise ValueError("Use a standard website address (no custom port)")
    try:
        host_ascii = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError("Website name has invalid characters")
    netloc = host_ascii + (f":{port}" if port else "")
    return urlunsplit((p.scheme.lower(), netloc, p.path or "", p.query, ""))


def is_public_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return a.is_global and not a.is_multicast


async def resolve_host(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    seen, out = set(), []
    for fam, _t, _p, _c, sockaddr in infos:
        ip = sockaddr[0].split("%")[0]
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    # prefer IPv4 first (broadest reachability from EC2)
    out.sort(key=lambda i: ":" in i)
    return out


def _pinned(url: str, ip: str) -> tuple[str, dict, dict]:
    p = urlsplit(url)
    host = p.hostname
    ip_host = f"[{ip}]" if ":" in ip else ip
    netloc = ip_host + (f":{p.port}" if p.port else "")
    pinned = urlunsplit((p.scheme, netloc, p.path or "/", p.query, ""))
    headers = {"Host": host + (f":{p.port}" if p.port else ""), "User-Agent": USER_AGENT, "Accept": "*/*"}
    ext = {"sni_hostname": host} if p.scheme == "https" else {}
    return pinned, headers, ext


async def _status_for(client: httpx.AsyncClient, url: str, ip: str) -> tuple[int, Optional[str]]:
    pinned, headers, ext = _pinned(url, ip)
    r = await client.request("HEAD", pinned, headers=headers, extensions=ext)
    status, loc = r.status_code, r.headers.get("location")
    if status in (400, 403, 405, 501):            # some servers refuse HEAD — retry as GET, body unread
        async with client.stream("GET", pinned, headers=headers, extensions=ext) as g:
            status, loc = g.status_code, g.headers.get("location")
    return status, loc


def _classify(status: int) -> tuple[str, bool, str]:
    if status < 400:
        return "live", True, "Website is live"
    if status in (401, 403, 429):
        return "restricted", True, "Website is live (it limits automated checks)"
    if status in (404, 410):
        return "not_found", False, "That page wasn't found — check the address"
    return "error", False, f"The website responded with an error ({status})"


async def check_website(raw: str, *, resolver: Callable[[str], Awaitable[list[str]]] = resolve_host,
                        transport: Optional[httpx.AsyncBaseTransport] = None,
                        allow_private: bool = False) -> dict:
    """Returns {ok, kind, message, url, final_url, status}. Never raises for
    network problems; `allow_private` exists only for tests."""
    try:
        url = normalize_url(raw)
    except ValueError as e:
        return {"ok": False, "kind": "invalid", "message": str(e), "url": None, "final_url": None, "status": None}
    cur, status = url, None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, transport=transport) as client:
            for _hop in range(MAX_REDIRECTS + 1):
                host = urlsplit(cur).hostname
                ips = await resolver(host)
                if not ips:
                    raise LookupError(host)
                if not allow_private and any(not is_public_ip(i) for i in ips):
                    raise Blocked(host)
                status, loc = await _status_for(client, cur, ips[0])
                if status in _REDIRECTS and loc:
                    cur = normalize_url(urljoin(cur, loc))      # re-validates scheme/port/host form
                    continue
                kind, ok, msg = _classify(status)
                return {"ok": ok, "kind": kind, "message": msg, "url": url, "final_url": cur, "status": status}
            return {"ok": False, "kind": "error", "message": "Too many redirects — check the address",
                    "url": url, "final_url": cur, "status": status}
    except Blocked:
        return {"ok": False, "kind": "blocked", "message": "That address can't be checked", "url": url, "final_url": None, "status": None}
    except (LookupError, socket.gaierror):
        return {"ok": False, "kind": "unreachable", "message": "We couldn't find this website — check the spelling",
                "url": url, "final_url": None, "status": None}
    except ValueError:                                           # bad redirect target
        return {"ok": False, "kind": "error", "message": "The website redirects somewhere we can't check",
                "url": url, "final_url": None, "status": status}
    except httpx.HTTPError:
        return {"ok": False, "kind": "unreachable", "message": "We couldn't reach this website right now — check the address",
                "url": url, "final_url": None, "status": None}
