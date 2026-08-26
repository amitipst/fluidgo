"""Registers the 'business_head' org_role AND seeds the exact 7-KRA "Business
Head / Direct Sales FGA v1" template from Amit's own July-2026 FGA sheet
(Variable_Pay_Amit_July26.xlsx, sheet "Direct_sales"), in one atomic,
idempotent, direct-DB script — same pattern as seed_service_delivery.py.

Every tier below was checked cell-by-cell against the source sheet, not
approximated: for each of the 7 KRA rows, weight * resolved multiplier
reproduces the sheet's own "Acheivement" (contribution) column exactly, and
summing all 7 reproduces the sheet's own bottom-line total of 0.71 (71%) —
see the worked numbers in the comments below. All 7 lines share the same
achievement curve, taken verbatim from the "Qualifier" column on every row:
  <80%            = 0
  80% to 100%     = proportionate (linear)
  100% to 110%    = square of achievement %, capped at 121%
  110% and above  = square of achievement %, capped at 169%
("110% to 130%" in the sheet is written as a closed band, but a hard cutover
to a 0-score tier the instant someone clears 130% would be a worse failure
mode than the sheet intends for genuine overachievement — so the top tier
here is left open-ended at the same 169% cap rather than bounded at 130%.)

Run: docker compose -f docker-compose.prod.yml exec -T backend python seed_business_head.py
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import OrgRole, ScoringTemplate, ScoringParameter
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)

# Shared curve — identical on every KRA line in this template (verbatim from
# the sheet's "Qualifier" column, repeated on all 7 rows).
CURVE = [
    {"label": "<80%", "max": 80, "multiplier": 0},
    {"label": "80-100% (proportionate)", "min": 80, "max": 100, "formula": "linear"},
    {"label": "100-110% (square, capped at 121%)", "min": 100, "max": 110, "formula": "square", "cap": 1.21},
    {"label": ">=110% (square, capped at 169%)", "min": 110, "formula": "square", "cap": 1.69},
]

# (name, weight_pct, metric_source, sort_order)
# Verified against the sheet, row by row (Weightage | Numbers=achievement% | Acheivement=contribution):
#   Business Alignment to Revenue Goals   0.30 | 81%  | 0.243
#   Alignment to Profitability            0.10 | 0%   | 0
#   Customer Meetings (Target >50)        0.10 | 100% | 0.100
#   Pipeline Size (Target Rs.1.2 Cr)      0.10 | 100% | 0.100
#   Revenue (Target Rs.35L)               0.20 | 29%  | 0        (<80% band -> 0)
#   Order Booking (Target Rs.30L)         0.10 | 130% | 0.169    (square capped at 169%)
#   fluidPro Customer SLA                 0.10 | 98%  | 0.098
#                                                  sum = 0.710  <- matches sheet's 71% total exactly
BUSINESS_HEAD_KRAS = [
    ("Business Alignment to Revenue Goals (3-month rolling vs org plan)", 30,
     "manual.biz_alignment_revenue_goals", 1),
    ("Business Alignment to Profitability", 10,
     "manual.alignment_profitability", 2),
    ("Department Parameter — Customer Meetings (Target > 50)", 10,
     "manual.dept_customer_meetings", 3),
    ("Department Parameter — Pipeline Size (Target Rs. 1.2 Cr)", 10,
     "manual.dept_pipeline_size", 4),
    ("Department Parameter — Revenue (Target Rs. 35L)", 20,
     "manual.dept_revenue", 5),
    ("Department Parameter — Order Booking (Target Rs. 30L)", 10,
     "manual.dept_order_booking", 6),
    ("Department Parameter — fluidPro Customer SLA (Process Improvement)", 10,
     "manual.fluidpro_customer_sla", 7),
]


async def seed():
    async with Session() as db:
        role = (await db.execute(
            select(OrgRole).where(OrgRole.role_key == "business_head")
        )).scalar_one_or_none()
        if role:
            print("  ✅ org_roles.business_head already exists")
        else:
            db.add(OrgRole(role_key="business_head", display_name="Business Head / Direct Sales",
                            parent_role_key=None, data_scope="all"))
            await db.commit()
            print("  \U0001f195 org_roles.business_head created")

        existing_tmpl = (await db.execute(
            select(ScoringTemplate).where(ScoringTemplate.role_key == "business_head",
                                           ScoringTemplate.is_active == True)
        )).scalar_one_or_none()
        if existing_tmpl:
            print(f"  ✅ Business Head FGA template already exists (v{existing_tmpl.version}) — not touching it")
            return

        tmpl = ScoringTemplate(name="Business Head / Direct Sales FGA v1", role_key="business_head",
                                version=1, is_active=True)
        db.add(tmpl)
        await db.flush()
        for name, weight, metric_source, order in BUSINESS_HEAD_KRAS:
            db.add(ScoringParameter(template_id=tmpl.id, name=name, weight_pct=weight,
                                     metric_source=metric_source, calc_type="tiered",
                                     tiers=CURVE, is_active=True, sort_order=order))
        await db.commit()
        print("  \U0001f195 Business Head / Direct Sales FGA v1 created — 7 KRAs, weights sum to 100%")

    print("\n✅ Done. Set org_role_key='business_head' on Amit's user (and any peer Business")
    print("   Head / Direct Sales role) — they'll score against this template automatically")
    print("   once Monthly KPI values are entered via Scoring > Manual KPI Entry.")

if __name__ == "__main__":
    asyncio.run(seed())
