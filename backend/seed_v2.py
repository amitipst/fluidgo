"""fluidGo v2 seed — org-role hierarchy + default Sales/PreSales FGA scoring templates.
Idempotent: safe to re-run, skips rows that already exist (same pattern as seed.py).
Run: python seed_v2.py  (from backend/ directory, with DATABASE_URL set)
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import OrgRole, ScoringTemplate, ScoringParameter, User, Base
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)

# (role_key, display_name, parent_role_key, data_scope)
ORG_ROLES = [
    ("sales",         "Sales",          "manager",       "own"),
    ("presales",      "PreSales",       "manager",       "own"),
    ("manager",       "Manager",        "bu_head",       "team"),
    ("bu_head",       "BU Head",        "practice_head", "bu"),
    ("practice_head", "Practice Head",  None,            "all"),
    ("hr",            "HR",             None,            "all"),
    ("admin",         "Admin",          None,            "all"),
    ("super_admin",   "Super Admin",    None,            "all"),
]

# Default weights are exactly the numbers from the product spec — editable later via
# /api/scoring/templates, never hardcoded in scoring_engine.py itself.
SALES_FGA = [
    ("Business Generation",      40, "revenue.target_achievement_pct", 1),
    ("Sales Execution",          25, "activity.rigor_avg",             2),
    ("Pipeline Quality",         20, "pipeline.bant_avg",              3),
    ("Professional Excellence",  15, "quality.self_score_avg",         4),
]
PRESALES_FGA = [
    ("Solution Support",       35, "presales.support_activity_pct", 1),
    ("Technical Conversion",   35, "presales.win_rate_pct",         2),
    # Knowledge Excellence has no dedicated data source yet (training/certifications
    # aren't captured anywhere) — proxied via self-scoring until that capture exists.
    ("Knowledge Excellence",   15, "quality.self_score_avg",        3),
    ("Operational Excellence", 15, "activity.dsr_compliance_pct",   4),
]

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        # org_roles is self-referencing (parent_role_key -> org_roles.role_key).
        # SQLAlchemy batches same-table inserts into one executemany, so a child row
        # can be sent before its parent row in the same batch and violate the FK.
        # Two passes avoids that: insert every row with parent_role_key=None first,
        # then backfill the real parent once all role_keys exist.
        existing_roles = {r[0] for r in (await db.execute(select(OrgRole.role_key))).all()}
        new_roles = [(role_key, display_name, parent, scope)
                     for role_key, display_name, parent, scope in ORG_ROLES if role_key not in existing_roles]
        for role_key, display_name, _parent, scope in new_roles:
            db.add(OrgRole(role_key=role_key, display_name=display_name, parent_role_key=None, data_scope=scope))
        await db.commit()

        for role_key, _display_name, parent, _scope in new_roles:
            if parent:
                role = (await db.execute(select(OrgRole).where(OrgRole.role_key == role_key))).scalar_one()
                role.parent_role_key = parent
        await db.commit()

        async def ensure_template(name: str, role_key: str, params: list):
            existing = (await db.execute(
                select(ScoringTemplate).where(ScoringTemplate.role_key == role_key,
                                               ScoringTemplate.is_active == True)
            )).scalar_one_or_none()
            if existing:
                return
            tmpl = ScoringTemplate(name=name, role_key=role_key, version=1, is_active=True)
            db.add(tmpl)
            await db.flush()
            for pname, weight, source, order in params:
                db.add(ScoringParameter(template_id=tmpl.id, name=pname, weight_pct=weight,
                                         metric_source=source, calc_type="pct", sort_order=order))

        await ensure_template("Sales FGA", "sales", SALES_FGA)
        await ensure_template("PreSales FGA", "presales", PRESALES_FGA)
        await db.commit()

        # Bootstrap org_role_key on the existing seed.py users so there's at least one
        # super_admin able to reach /api/scoring/templates and /api/roles from day one —
        # without this, no seeded user could ever assign org roles to anyone (nothing
        # in the DB would have org_role_key='admin'/'super_admin' after a fresh migrate).
        BOOTSTRAP_MAP = {
            "amit@wepsol.com":     "super_admin",
            "manager@fluidpro.in": "manager",
            "danish@fluidpro.in":  "sales",
            "inside@fluidpro.in":  "presales",
        }
        for email, org_role_key in BOOTSTRAP_MAP.items():
            u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if u and not u.org_role_key:
                u.org_role_key = org_role_key
        await db.commit()
        print("✅ v2 seed complete — org_roles + Sales/PreSales FGA templates loaded.")

if __name__ == "__main__":
    asyncio.run(seed())
