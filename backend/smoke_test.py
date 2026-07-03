#!/usr/bin/env python3
"""
fluidGo Smoke Test Suite — v1.0.0
==================================
Runs fast (~30s) against a live server.
Used by CI before every release and after every deploy.

Usage:
  python smoke_test.py                          # local (http://localhost)
  python smoke_test.py --base https://uat.dsr.fluidpro.in
  python smoke_test.py --base https://dsr.fluidpro.in

Exit code 0 = all pass, 1 = failures found.
"""
import sys
import time
import argparse
import httpx

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="fluidGo smoke test")
parser.add_argument("--base", default="http://localhost", help="Base URL")
parser.add_argument("--timeout", type=int, default=15)
args = parser.parse_args()
BASE = args.base.rstrip("/")
print(f"\n{'='*60}")
print(f"  fluidGo Smoke Test Suite")
print(f"  Target: {BASE}")
print(f"{'='*60}")

# ── Test runner ───────────────────────────────────────────────────────────────
results: list[tuple[str, str, str]] = []

def check(name: str, condition: bool, detail: str = "") -> bool:
    status = "✅ PASS" if condition else "❌ FAIL"
    results.append((status, name, detail))
    print(f"  {status} | {name}" + (f" — {detail}" if detail else ""))
    return condition

def section(title: str):
    print(f"\n── {title} {'─'*(55-len(title))}")

def api_get(path: str, token: str = "", expected: int = 200):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = httpx.get(f"{BASE}/api{path}", headers=headers, timeout=args.timeout)
        return r, r.status_code == expected
    except Exception as e:
        return None, False

def api_post(path: str, body: dict, token: str = "", expected: int = 200):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = httpx.post(f"{BASE}/api{path}", json=body, headers=headers, timeout=args.timeout)
        return r, r.status_code in (expected, 200, 201)
    except Exception as e:
        return None, False

# ── SUITE 1: Infrastructure ───────────────────────────────────────────────────
section("1. Infrastructure")
r, ok = api_get("/health")
check("API health endpoint responds", ok)
if ok:
    check("Health returns status:ok", r.json().get("status") == "ok",
          f"got: {r.json()}")
    check("Version field present",    "version" in r.json())

# Frontend (check nginx proxy, not the backend base URL)
# When running from inside a Docker container, nginx is at http://nginx:80
# When running from outside, it's at the base URL itself
import os
nginx_url = os.getenv("NGINX_URL", BASE if not BASE.endswith(":8000") else "http://nginx")
try:
    fr = httpx.get(nginx_url, timeout=10, follow_redirects=True)
    check("Frontend serves HTML", "text/html" in fr.headers.get("content-type",""),
          f"HTTP {fr.status_code} from {nginx_url}")
except Exception as e:
    check("Frontend serves HTML", False, f"Cannot reach {nginx_url}: {e}")

# ── SUITE 2: Auth — all 5 roles ───────────────────────────────────────────────
section("2. Authentication (5 roles)")
CREDS = {
    "bu_head":     ("amit@wepsol.com",        "Admin@2026!"),
    "manager":     ("manager@fluidpro.in",     "Mgr@2026!"),
    "rep":         ("danish@fluidpro.in",      "Fluid@2026!"),
    "pre_sales":   ("sanjay.ps@fluidpro.in",   "Fluid@2026!"),
    "inside_sales":("inside@fluidpro.in",      "Inside@2026!"),
}
tokens: dict[str, str] = {}
user_ids: dict[str, str] = {}
for role, (email, pwd) in CREDS.items():
    r, ok = api_post("/auth/login", {"email": email, "password": pwd})
    if ok and r:
        tokens[role] = r.json().get("access_token", "")
        user_ids[role] = r.json().get("user", {}).get("id", "")
        got_role = r.json().get("user", {}).get("role", "")
        check(f"Login {role}", True, f"role={got_role}")
    else:
        check(f"Login {role}", False, f"HTTP {r.status_code if r else 'N/A'}")

check("All 5 tokens obtained", len(tokens) == 5, f"got {len(tokens)}/5")

# ── SUITE 3: DSR Workflow ─────────────────────────────────────────────────────
section("3. DSR Workflow")
today = time.strftime("%Y-%m-%d")
tok_rep = tokens.get("rep", "")
if tok_rep:
    r, ok = api_post("/dsr", {
        "date": today, "status": "working",
        "visits": 2, "calls": 5, "followups": 10,
        "new_leads": 1, "proposals": 1
    }, tok_rep)
    check("Rep: submit DSR", ok, f"HTTP {r.status_code if r else 'N/A'}")
    if ok:
        data = r.json()
        check("Rep: rigor score returned", data.get("rigor_score", 0) > 0,
              f"rigor={data.get('rigor_score')}")
        check("Rep: dsr_type = sales",    data.get("dsr_type") == "sales")

# Pre-sales DSR
tok_ps = tokens.get("pre_sales", "")
if tok_ps:
    r, ok = api_post("/dsr", {
        "date": today, "status": "working",
        "demos_conducted": 1, "pocs_conducted": 1,
        "proposals_supported": 2, "tech_discussions": 3,
    }, tok_ps)
    check("Pre-Sales: submit DSR", ok)
    if ok:
        check("Pre-Sales: dsr_type = presales",
              r.json().get("dsr_type") == "presales")

# ── SUITE 4: Role-Based Access Control ───────────────────────────────────────
section("4. RBAC Security")
tok_rep = tokens.get("rep", "")
BLOCKED = [
    ("/analytics/team",       "Rep blocked from team analytics"),
    ("/dsr/team?date="+today, "Rep blocked from team DSR"),
    ("/users",                "Rep blocked from user management"),
    ("/scoring/templates",    "Rep blocked from scoring admin"),
]
for path, label in BLOCKED:
    r, _ = api_get(path, tok_rep)
    check(label, r is not None and r.status_code == 403,
          f"got HTTP {r.status_code if r else 'N/A'}")

r, _ = api_post("/fga/freeze", {"period": "2026-07"}, tok_rep)
check("Rep blocked from FGA freeze",
      r is not None and r.status_code == 403,
      f"got HTTP {r.status_code if r else 'N/A'}")

# ── SUITE 5: Dashboard & Analytics ───────────────────────────────────────────
section("5. Dashboard & Analytics")
tok_bu = tokens.get("bu_head", "")
if tok_bu:
    r, ok = api_get("/analytics/dashboard?month=2026-05", tok_bu)
    check("BU Head: dashboard with May data", ok)
    if ok:
        d = r.json()
        check("Dashboard: calls > 0",    d.get("total_calls", 0) > 0,
              f"calls={d.get('total_calls')}")
        check("Dashboard: avg_rigor > 0", d.get("avg_rigor", 0) > 0,
              f"rigor={d.get('avg_rigor')}")

    r, ok = api_get("/analytics/revenue?period=2026-05", tok_bu)
    check("BU Head: revenue analytics", ok)
    if ok:
        d = r.json()
        check("Revenue: target set",   d.get("target", 0) > 0,
              f"target=₹{d.get('target')}")
        check("Revenue: revenue calc", "revenue" in d)

# ── SUITE 6: Meetings, Leads, Pipeline ───────────────────────────────────────
section("6. Core Data Endpoints")
tok_rep = tokens.get("rep", "")
for label, path in [
    ("Meetings list", "/meetings"),
    ("Leads list",    "/leads"),
    ("Pipeline list", "/pipeline"),
    ("Opportunities", "/opportunities"),
]:
    r, ok = api_get(path, tok_rep)
    check(label, ok, f"HTTP {r.status_code if r else 'N/A'}")

# ── SUITE 7: FGA & Incentives ─────────────────────────────────────────────────
section("7. FGA & Incentives")
tok_bu = tokens.get("bu_head", "")
if tok_bu:
    r, ok = api_get("/fga/pending?period=2026-05", tok_bu)
    check("FGA pending list accessible", ok)

    r, ok = api_get("/scoring/templates", tok_bu)
    check("Scoring templates accessible", ok)
    if ok:
        templates = r.json()
        check("Sales FGA template exists",
              any(t.get("role_key") == "sales" for t in templates))

    r, ok = api_get("/incentives/schemes?period=2026-07", tok_rep)
    check("Incentive schemes visible to rep", ok)

    r, ok = api_get("/incentives/leaderboard?period=2026-07", tok_rep)
    check("Leaderboard accessible", ok)
    if ok:
        board = r.json()
        hr_in_board = any(u.get("role") in ("hr","finance") for u in board)
        check("HR/Finance excluded from leaderboard", not hr_in_board,
              f"found HR/Finance: {hr_in_board}")

# ── SUITE 8: Manager workflow ─────────────────────────────────────────────────
section("8. Manager Workflow")
tok_mgr = tokens.get("manager", "")
if tok_mgr:
    r, ok = api_get("/analytics/team", tok_mgr)
    check("Manager sees team", ok)
    if ok:
        team = r.json()
        check("Team is BU-scoped (West only)",
              all(m.get("bu") == "West" for m in team),
              f"BUs seen: {set(m.get('bu') for m in team)}")

    r, ok = api_get(f"/dsr/team?date={today}", tok_mgr)
    check("Manager sees team DSR compliance", ok)

# ── RESULTS ───────────────────────────────────────────────────────────────────
total  = len(results)
passed = sum(1 for r in results if r[0].startswith("✅"))
failed = sum(1 for r in results if r[0].startswith("❌"))

print(f"\n{'='*60}")
print(f"  SMOKE TEST RESULTS — {BASE}")
print(f"{'='*60}")
print(f"  Total:  {total}")
print(f"  Passed: {passed} ✅")
print(f"  Failed: {failed} ❌")
print(f"  Rate:   {passed/total*100:.0f}%")

if failed:
    print(f"\n  ❌ FAILURES:")
    for status, name, detail in results:
        if status.startswith("❌"):
            print(f"    • {name}" + (f" — {detail}" if detail else ""))
    print()
    sys.exit(1)
else:
    print(f"\n  ✅ All checks passed. Ready to release.\n")
    sys.exit(0)
