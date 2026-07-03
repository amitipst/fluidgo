"""Quick fixes: reseed incentive schemes, boost meeting/pipeline counts to target"""
import asyncio, random, sys
from datetime import date, timedelta
from decimal import Decimal
sys.path.insert(0, '/app')
random.seed(99)

COMPANIES = [
    "Nido Home Finance","Vakksh Capital","Eagle SPS","New Era Cleantech",
    "MRR Hospital","Autosys","HDFC Securities","Axis Bank","Bajaj Finserv",
    "Muthoot Finance","Tech Mahindra","Infosys BPM","Hexaware","Cognizant"
]
PRACTICES = ["Cloud & Security","Microsoft","Managed Services","Network","EUC"]

async def fix():
    from app.database import AsyncSessionLocal
    from app.models import (User, Meeting, PipelineDeal, IncentiveScheme)
    from sqlalchemy import select, func, delete

    async with AsyncSessionLocal() as db:
        # ── 1. Add incentive schemes (were wiped by seed_v3) ────────────────
        print("🎮 Re-creating incentive schemes...")
        users = (await db.execute(select(User).where(User.role == "bu_head"))).scalars().all()
        bu_head = users[0] if users else None

        if bu_head:
            for period in ["2026-05","2026-06","2026-07"]:
                schemes = [
                    ("Calls Blitz","calls",100,"points",500,None),
                    ("Lead Machine","new_leads",10,"cash",5000,None),
                    ("BANT Masters","bant_meetings",5,"badge",None,"bant_master"),
                    ("Rigor Champion","rigor_avg",75,"points",300,None),
                    ("Deal Closer","closed_won_value",500000,"cash",10000,None),
                ]
                for name, metric, target, rtype, rvalue, rbadge in schemes:
                    db.add(IncentiveScheme(
                        created_by=bu_head.id, bu=bu_head.bu, business=bu_head.business,
                        scope="bu", name=f"{period} {name}", period=period,
                        status="active", metric=metric, target_value=Decimal(target),
                        reward_type=rtype,
                        reward_value=Decimal(rvalue) if rvalue else None,
                        reward_badge=rbadge
                    ))
            await db.commit()

        cnt = (await db.execute(select(func.count()).select_from(IncentiveScheme))).scalar()
        print(f"   ✅ {cnt} schemes created")

        # ── 2. Boost meetings to 150+ ───────────────────────────────────────
        current_mtgs = (await db.execute(select(func.count()).select_from(Meeting))).scalar()
        need = max(0, 160 - current_mtgs)
        print(f"🤝 Adding {need} more meetings (current: {current_mtgs})...")

        all_reps = (await db.execute(
            select(User).where(User.role.in_(["rep","inside_sales"]))
        )).scalars().all()

        for i in range(need):
            rep = random.choice(all_reps)
            dt  = date(2026, random.randint(4,7), random.randint(1,28))
            try:
                dt = date(dt.year, dt.month, min(dt.day, 28))  # safe for all months
            except: dt = date(2026, 6, 15)
            bant = [random.random()>0.35 for _ in range(4)]
            filled = sum(bant)
            pct_map = {4:85,3:62,2:38,1:15,0:5}
            db.add(Meeting(
                user_id=rep.id,
                date=dt,
                company=random.choice(COMPANIES),
                contact_name=f"Prospect {i+1}",
                meeting_type=random.choice(["F2F","Virtual","Call"]),
                discussion=f"Discussed {random.choice(PRACTICES)} requirements",
                opportunity=random.random()>0.3,
                bant_budget=bant[0], bant_authority=bant[1],
                bant_need=bant[2], bant_timeline=bant[3],
                ai_intent_score="hot" if filled>=3 else "warm" if filled>=2 else "cold",
                ai_closure_pct=pct_map[filled]
            ))
        await db.commit()
        final_mtgs = (await db.execute(select(func.count()).select_from(Meeting))).scalar()
        print(f"   ✅ {final_mtgs} total meetings")

        # ── 3. Boost pipeline to 100+ ───────────────────────────────────────
        current_pipeline = (await db.execute(select(func.count()).select_from(PipelineDeal))).scalar()
        need_p = max(0, 105 - current_pipeline)
        print(f"💼 Adding {need_p} more pipeline deals (current: {current_pipeline})...")

        for i in range(need_p):
            rep = random.choice(all_reps)
            stage = random.choice(["cold","warm","hot","closed_won","closed_lost"])
            db.add(PipelineDeal(
                user_id=rep.id,
                company=random.choice(COMPANIES),
                stage=stage,
                deal_value=Decimal(random.choice([200000,350000,500000,750000,1000000])),
                closure_eta=date(2026, random.randint(5,9), 28),
                todays_update="Ongoing discussion",
                next_step="Follow up next week",
                ai_closure_pct={"cold":10,"warm":40,"hot":70,"closed_won":100,"closed_lost":0}.get(stage,50)
            ))
        await db.commit()
        final_pipeline = (await db.execute(select(func.count()).select_from(PipelineDeal))).scalar()
        print(f"   ✅ {final_pipeline} total pipeline deals")

        print("\n✅ Fixes applied")

asyncio.run(fix())
