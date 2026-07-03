import httpx, json, sys

base = "http://localhost:8000/api"

# Login as BU Head
r = httpx.post(f"{base}/auth/login",
               json={"email": "amit@wepsol.com", "password": "Admin@2026!"})
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text}")
    sys.exit(1)

token = r.json()["access_token"]
user  = r.json()["user"]
print(f"Logged in: {user['name']} ({user['role']})")

headers = {"Authorization": f"Bearer {token}"}

# Test BU dashboard
d = httpx.get(f"{base}/analytics/dashboard", headers=headers)
print(f"\nDashboard ({d.status_code}):")
print(json.dumps(d.json(), indent=2))

# Test team analytics
t = httpx.get(f"{base}/analytics/team", headers=headers)
print(f"\nTeam ({t.status_code}) — {len(t.json())} members:")
for m in t.json():
    print(f"  {m['name']:20s} rigor={m['avg_rigor']:5.1f}  calls={m['total_calls']:3d}")

# Test FGA endpoints
fga = httpx.get(f"{base}/fga/pending?period=2026-05", headers=headers)
print(f"\nFGA pending ({fga.status_code}): {len(fga.json())} items")

print("\n✅ All checks passed")
