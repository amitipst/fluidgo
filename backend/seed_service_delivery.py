"""Registers the 'service_delivery' org_role AND seeds the exact 6-KRA
"Service Delivery FGA v1" template from Hemant's May-2026 sheet, in one
atomic, idempotent, direct-DB script — replaces seed_sdm_fga.py, which hit
a real bug: scoring_templates.role_key has an enforced FK to org_roles.role_key
(see 0003_v2_foundation.py), and nothing had ever inserted a 'service_delivery'
row there, so BOTH the seed script's HTTP POST and the Scoring Admin "+New
Template" UI button were failing with a 500 (FK violation) for ANY role_key
that isn't already in org_roles — the same bug will bite the next brand-new
role_key someone tries via the UI, not just this one. Same idempotent,
direct-DB pattern as seed_v2.py (safe to re-run).

Run: docker compose -f docker-compose.prod.yml exec -T backend python seed_service_delivery.py
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import OrgRole, ScoringTemplate, ScoringParameter
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)

SDM_TIERS = [
    ("Monthly Payment Collection (as per due date)", 20, "manual.payment_collection_pct", 1,
     [{"label": "<80%", "max": 80, "multiplier": 0},
      {"label": ">=80% (square of achievement)", "min": 80, "formula": "square"}]),
    ("SLA Compliance (Overall Customer SLA)", 20, "manual.sla_compliance_pct", 2,
     [{"label": "<95%", "max": 95, "multiplier": 0},
      {"label": "95-97%", "min": 95, "max": 97, "multiplier": 1},
      {"label": ">97-<99%", "min": 97, "max": 99, "multiplier": 1.25},
      {"label": ">=99%", "min": 99, "multiplier": 1.5}]),
    ("Customer CSAT / Escalation Review", 20, "manual.escalation_count", 3,
     [{"label": ">=2 Escalations", "min": 2, "multiplier": 0},
      {"label": "1 Escalation", "min": 1, "max": 2, "multiplier": 0.5},
      {"label": "0 Escalations", "min": 0, "max": 1, "multiplier": 1}]),
    ("Ticket >3 Days (Incident Requests)", 10, "manual.ticket_within_3days_pct", 4,
     [{"label": "<90%", "max": 90, "multiplier": 0},
      {"label": "90-95%", "min": 90, "max": 95, "multiplier": 1},
      {"label": "95-98%", "min": 95, "max": 98, "multiplier": 1.25},
      {"label": ">=98%", "min": 98, "multiplier": 1.5}]),
    ("Monthly Review Compliance", 20, "manual.review_compliance_pct", 5,
     [{"label": "<95%", "max": 95, "multiplier": 0},
      {"label": "95-97%", "min": 95, "max": 97, "multiplier": 1},
      {"label": "97-99%", "min": 97, "max": 99, "multiplier": 1.25},
      {"label": ">=99%", "min": 99, "multiplier": 1.5}]),
    ("Resource Attrition (against total reportees)", 10, "manual.attrition_pct", 6,
     [{"label": ">10%", "min": 10, "multiplier": 0},
      {"label": "5-10%", "min": 5, "max": 10, "multiplier": 0.5},
      {"label": "2-5%", "min": 2, "max": 5, "multiplier": 0.75},
      {"label": "0-2%", "min": 0.01, "max": 2, "multiplier": 1},
      {"label": "0% (no attrition)", "min": -0.01, "max": 0.01, "multiplier": 1.25}]),
]


async def seed():
    async with Session() as db:
        role = (await db.execute(
            select(OrgRole).where(OrgRole.role_key == "service_delivery")
        )).scalar_one_or_none()
        if role:
            print("  ✅ org_roles.service_delivery already exists")
        else:
            db.add(OrgRole(role_key="service_delivery", display_name="Service Delivery",
                            parent_role_key="manager", data_scope="team"))
            await db.commit()
            print("  🆕 org_roles.service_delivery created")

        existing_tmpl = (await db.execute(
            select(ScoringTemplate).where(ScoringTemplate.role_key == "service_delivery",
                                           ScoringTemplate.is_active == True)
        )).scalar_one_or_none()
        if existing_tmpl:
            print(f"  ✅ Service Delivery FGA template already exists (v{existing_tmpl.version}) — not touching it")
            return

        tmpl = ScoringTemplate(name="Service Delivery FGA v1", role_key="service_delivery",
                                version=1, is_active=True)
        db.add(tmpl)
        await db.flush()
        for name, weight, metric_source, order, tiers in SDM_TIERS:
            db.add(ScoringParameter(template_id=tmpl.id, name=name, weight_pct=weight,
                                     metric_source=metric_source, calc_type="tiered",
                                     tiers=tiers, is_active=True, sort_order=order))
        await db.commit()
        print("  🆕 Service Delivery FGA v1 created — 6 KRAs, weights sum to 100%")

    print("\n✅ Done. Assign a user role='service_delivery_manager' — they'll score against")
    print("   this template automatically once Monthly KPI values are entered.")

if __name__ == "__main__":
    asyncio.run(seed())
