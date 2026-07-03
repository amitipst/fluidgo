"""Set revenue targets for Danish and seed a sample incentive scheme.
Run: docker compose exec backend python seed_targets.py
"""
import httpx, time, json
time.sleep(1)
base = "http://localhost:8000/api"

# Login as BU Head
r = httpx.post(f"{base}/auth/login", json={"email":"amit@wepsol.com","password":"Admin@2026!"})
token   = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get Danish's user_id
users = httpx.get(f"{base}/users", headers=headers).json()
danish = next((u for u in users if "Danish" in u["name"]), None)
if not danish:
    print("❌ Danish not found — run seed.py first")
    exit(1)
print(f"✅ Found: {danish['name']} ({danish['id']})")

# Set revenue target for Danish — May 2026: ₹10,00,000
for period in ["2026-05", "2026-06", "2026-07"]:
    t = httpx.post(f"{base}/analytics/revenue/targets", headers=headers,
                   json={"user_id": danish["id"], "period": period, "target_amount": 1000000})
    print(f"  Target {period}: {t.status_code} → ₹10,00,000")

# Create sample incentive schemes for July 2026
schemes = [
    {
        "name": "July Calls Blitz 🔥",
        "description": "Hit 5+ calls every working day this month. Top caller gets Deal King badge.",
        "period": "2026-07",
        "scope": "bu",
        "metric": "calls",
        "target_value": 100,
        "reward_type": "badge",
        "reward_badge": "top_caller"
    },
    {
        "name": "Lead Machine Challenge 🎯",
        "description": "Generate 10 qualified leads in July. Win ₹5,000 cash bonus.",
        "period": "2026-07",
        "scope": "bu",
        "metric": "new_leads",
        "target_value": 10,
        "reward_type": "cash",
        "reward_value": 5000
    },
    {
        "name": "BANT Masters League 🧠",
        "description": "Close 3 fully BANT-qualified meetings (all 4 criteria). Earn BANT Master badge.",
        "period": "2026-07",
        "scope": "bu",
        "metric": "bant_meetings",
        "target_value": 3,
        "reward_type": "badge",
        "reward_badge": "bant_master"
    },
    {
        "name": "Rigor Champion 2026 ⚡",
        "description": "Maintain average rigor score above 75 for the whole month.",
        "period": "2026-07",
        "scope": "bu",
        "metric": "rigor_avg",
        "target_value": 75,
        "reward_type": "points",
        "reward_value": 500
    }
]

print("\n🎮 Creating incentive schemes for July 2026...")
for s in schemes:
    resp = httpx.post(f"{base}/incentives/schemes", headers=headers, json=s)
    print(f"  {resp.status_code} → {s['name']}")

# Re-freeze May 2026 FGA to recalculate with target
print("\n❄️  Re-freezing May 2026 FGA (now with revenue target)...")
fga = httpx.post(f"{base}/fga/freeze", json={"period":"2026-05"}, headers=headers)
print(f"  {fga.status_code} → {fga.text[:200]}")

# Show updated scores
print("\n📊 May 2026 FGA scores after target set:")
pending = httpx.get(f"{base}/fga/pending?period=2026-05", headers=headers).json()
for p in pending:
    print(f"  {p['name']:20s}  score={p.get('score',0):.1f}  status={p['approval_status']}")

print("\n✅ All done. Refresh http://localhost to see updated data.")
