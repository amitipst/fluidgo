"""Seeds the Service Delivery Manager FGA template — the exact 6 KRAs from
Hemant's May-2026 scorecard (Payment Collection, SLA Compliance, Escalation
Review, Ticket>3Days, Monthly Review Compliance, Resource Attrition), using
the new 'tiered' calc_type so weak/strong bands score below/above the base
weight, matching the source spreadsheet's multiplier logic exactly.

All 6 parameters are calc_type='tiered' with metric_source='manual.*' — the
SDM (or their manager) enters each period's achievement value on the Monthly
KPI Entry screen; nothing here is auto-computed from DSR data.

Run: docker compose exec backend python seed_sdm_fga.py
"""
import httpx, time
time.sleep(1)
base = "http://localhost:8000/api"

r = httpx.post(f"{base}/auth/login", json={
    "email": "amit.singh@wepsol.com", "password": "Admin@2026!"
})
r.raise_for_status()
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

template = {
    "name": "Service Delivery FGA v1",
    "role_key": "service_delivery",
    "parameters": [
        {
            "name": "Monthly Payment Collection (as per due date)",
            "weight_pct": 20, "calc_type": "tiered", "sort_order": 1,
            "metric_source": "manual.payment_collection_pct",
            "tiers": [
                {"label": "<80%", "max": 80, "multiplier": 0},
                {"label": ">=80% (square of achievement)", "min": 80, "formula": "square"},
            ],
        },
        {
            "name": "SLA Compliance (Overall Customer SLA)",
            "weight_pct": 20, "calc_type": "tiered", "sort_order": 2,
            "metric_source": "manual.sla_compliance_pct",
            "tiers": [
                {"label": "<95%", "max": 95, "multiplier": 0},
                {"label": "95-97%", "min": 95, "max": 97, "multiplier": 1},
                {"label": ">97-<99%", "min": 97, "max": 99, "multiplier": 1.25},
                {"label": ">=99%", "min": 99, "multiplier": 1.5},
            ],
        },
        {
            "name": "Customer CSAT / Escalation Review",
            "weight_pct": 20, "calc_type": "tiered", "sort_order": 3,
            "metric_source": "manual.escalation_count",
            "tiers": [
                {"label": ">=2 Escalations", "min": 2, "multiplier": 0},
                {"label": "1 Escalation", "min": 1, "max": 2, "multiplier": 0.5},
                {"label": "0 Escalations", "min": 0, "max": 1, "multiplier": 1},
            ],
        },
        {
            "name": "Ticket >3 Days (Incident Requests)",
            "weight_pct": 10, "calc_type": "tiered", "sort_order": 4,
            "metric_source": "manual.ticket_within_3days_pct",
            "tiers": [
                {"label": "<90%", "max": 90, "multiplier": 0},
                {"label": "90-95%", "min": 90, "max": 95, "multiplier": 1},
                {"label": "95-98%", "min": 95, "max": 98, "multiplier": 1.25},
                {"label": ">=98%", "min": 98, "multiplier": 1.5},
            ],
        },
        {
            "name": "Monthly Review Compliance",
            "weight_pct": 20, "calc_type": "tiered", "sort_order": 5,
            "metric_source": "manual.review_compliance_pct",
            "tiers": [
                {"label": "<95%", "max": 95, "multiplier": 0},
                {"label": "95-97%", "min": 95, "max": 97, "multiplier": 1},
                {"label": "97-99%", "min": 97, "max": 99, "multiplier": 1.25},
                {"label": ">=99%", "min": 99, "multiplier": 1.5},
            ],
        },
        {
            "name": "Resource Attrition (against total reportees)",
            "weight_pct": 10, "calc_type": "tiered", "sort_order": 6,
            "metric_source": "manual.attrition_pct",
            "tiers": [
                {"label": ">10%", "min": 10, "multiplier": 0},
                {"label": "5-10%", "min": 5, "max": 10, "multiplier": 0.5},
                {"label": "2-5%", "min": 2, "max": 5, "multiplier": 0.75},
                {"label": "0-2%", "min": 0.01, "max": 2, "multiplier": 1},
                {"label": "0% (no attrition)", "min": -0.01, "max": 0.01, "multiplier": 1.25},
            ],
        },
    ],
}

resp = httpx.post(f"{base}/scoring/templates", headers=headers, json=template)
print(resp.status_code, resp.text[:500])
if resp.status_code == 200:
    print("\n✅ Service Delivery FGA v1 template created — role_key='service_delivery'")
    print("   Assign a user role='service_delivery_manager' and they'll automatically")
    print("   score against this template once Monthly KPI values are entered.")
else:
    print("\n❌ Failed — check the response above")
