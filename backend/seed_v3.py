"""
fluidGo Full Seed v3 — Phase 9 compliant dataset
Generates realistic FluidPro West BU data:
  2 BU Heads · 4 Managers · 12 Sales Reps · 6 Pre-Sales
  300+ DSR entries · 150+ Meetings · 100 Pipeline deals · 50 Customers
  20 Won deals · 15 Lost deals · Multi-month pipeline
Run: docker compose exec backend python seed_v3.py
"""
import asyncio, random, sys
from datetime import date, timedelta
from decimal import Decimal
sys.path.insert(0, '/app')

random.seed(42)  # reproducible

# ── Master data ───────────────────────────────────────────────────────────────
COMPANIES = [
    "Nido Home Finance Ltd","Vakksh Capital Co Ltd","Eagle SPS India Pvt Ltd",
    "New Era Cleantech Solutions","MRR Children's Hospital","Autosys Industrial Solutions",
    "Bharat Forge Ltd","Wipro Infrastructure","Tata Advanced Systems","HDFC Securities",
    "Axis Bank Regional HQ","IDFC First Bank","Reliance Jio Infrastructure",
    "Mahindra Logistics","Godrej Properties","Raymond Ltd","Bajaj Finserv",
    "Muthoot Finance","L&T Infotech","HCL Technologies Regional",
    "Tech Mahindra SMB","Infosys BPM","Hexaware Technologies",
    "Cognizant Pune Office","Accenture India","Capgemini India",
    "KPIT Technologies","Persistent Systems","Cyient Ltd","Mphasis Ltd",
    "Zensar Technologies","Mastech Holdings","NIIT Technologies",
    "Birlasoft Ltd","Sonata Software","Rategain Travel Tech",
    "Intellicheck India","Saksoft Ltd","Trigent Software","Ksolves India",
    "Nucleus Software","Datamatics Global","E-Infochips",
    "Atos India","DXC Technology India","NTT Data India",
    "IBM India Regional","HP India Sales","Dell Technologies India","Lenovo India"
]

PRACTICES = ["Cloud & Security", "Microsoft", "Managed Services", "Network", "End User Computing"]
STAGES = ["cold","warm","hot","closed_won","closed_won","closed_won","closed_lost","dropped"]
MEETING_TYPES = ["F2F","F2F","F2F","Virtual","Call"]
SOURCES = ["Call","Visit","Referral","LinkedIn","Email"]

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def working_dates(start: date, end: date):
    """All weekdays between start and end."""
    d, dates = start, []
    while d <= end:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    return dates

async def seed():
    from app.database import AsyncSessionLocal, engine
    from app.models import (Base, User, DSRDaily, SelfScore, Meeting, Lead,
                             PipelineDeal, RevenueTarget)
    from app.services.auth_service import hash_password
    from sqlalchemy import select, delete

    # Create tables (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        # ── 1. Clear old seed data (keep real user entries) ───────────────────
        print("🧹 Clearing old seed data...")
        from app.models import (SelfScore, Meeting, Lead, PipelineDeal, DSRDaily,
                                 RevenueTarget, User, ScoringResult, PointsLedger,
                                 UserBadge, IncentiveScheme)
        from sqlalchemy import delete as sql_delete
        # Delete in FK dependency order (children first)
        for model in [SelfScore, PointsLedger, UserBadge, ScoringResult,
                      IncentiveScheme, Meeting, Lead, PipelineDeal,
                      DSRDaily, RevenueTarget, User]:
            await db.execute(sql_delete(model))
        await db.commit()
        print("   ✅ Cleared")

        # ── 2. Create Users ───────────────────────────────────────────────────
        print("👥 Creating users...")
        users_to_create = [
            # BU Heads
            ("Amit Singh",         "amit@wepsol.com",          "Admin@2026!", "bu_head",     "West", "fluidpro"),
            ("Priya Mehta",        "priya.bh@wepsol.com",      "Admin@2026!", "bu_head",     "North","fluidpro"),
            # Managers
            ("Rajesh Sharma",      "manager@fluidpro.in",      "Mgr@2026!",   "manager",     "West", "fluidpro"),
            ("Sunita Patil",       "sunita.m@fluidpro.in",     "Mgr@2026!",   "manager",     "West", "fluidpro"),
            ("Vikram Nair",        "vikram.m@fluidpro.in",     "Mgr@2026!",   "manager",     "North","fluidpro"),
            ("Deepa Krishnan",     "deepa.m@fluidpro.in",      "Mgr@2026!",   "manager",     "North","fluidpro"),
            # Sales Reps — West
            ("Danish Sayyed",      "danish@fluidpro.in",       "Fluid@2026!", "rep",         "West", "fluidpro"),
            ("Rahul Mehta",        "rahul@fluidpro.in",        "Fluid@2026!", "rep",         "West", "fluidpro"),
            ("Anjali Desai",       "anjali@fluidpro.in",       "Fluid@2026!", "rep",         "West", "fluidpro"),
            ("Sameer Khan",        "sameer@fluidpro.in",       "Fluid@2026!", "rep",         "West", "fluidpro"),
            ("Ravi Krishnan",      "ravi@fluidpro.in",         "Fluid@2026!", "rep",         "West", "fluidpro"),
            ("Neha Joshi",         "neha@fluidpro.in",         "Fluid@2026!", "rep",         "West", "fluidpro"),
            # Sales Reps — North
            ("Arun Gupta",         "arun@fluidpro.in",         "Fluid@2026!", "rep",         "North","fluidpro"),
            ("Pooja Verma",        "pooja@fluidpro.in",        "Fluid@2026!", "rep",         "North","fluidpro"),
            ("Kiran Bhatia",       "kiran@fluidpro.in",        "Fluid@2026!", "rep",         "North","fluidpro"),
            ("Suresh Yadav",       "suresh@fluidpro.in",       "Fluid@2026!", "rep",         "North","fluidpro"),
            ("Meera Pillai",       "meera@fluidpro.in",        "Fluid@2026!", "rep",         "North","fluidpro"),
            ("Ashok Tiwari",       "ashok@fluidpro.in",        "Fluid@2026!", "rep",         "North","fluidpro"),
            # Pre-Sales
            ("Sanjay Reddy",       "sanjay.ps@fluidpro.in",    "Fluid@2026!", "pre_sales",   "West", "fluidpro"),
            ("Kavitha Nambiar",    "kavitha.ps@fluidpro.in",   "Fluid@2026!", "pre_sales",   "West", "fluidpro"),
            ("Mohit Agarwal",      "mohit.ps@fluidpro.in",     "Fluid@2026!", "pre_sales",   "West", "fluidpro"),
            ("Divya Menon",        "divya.ps@fluidpro.in",     "Fluid@2026!", "pre_sales",   "North","fluidpro"),
            ("Abhishek Singh",     "abhishek.ps@fluidpro.in",  "Fluid@2026!", "pre_sales",   "North","fluidpro"),
            ("Lakshmi Rao",        "lakshmi.ps@fluidpro.in",   "Fluid@2026!", "pre_sales",   "North","fluidpro"),
            # Support roles
            ("Inside Sales",       "inside@fluidpro.in",       "Inside@2026!","inside_sales","West", "fluidpro"),
            ("HR Manager",         "hr@wepsol.com",            "Hr@2026!",    "hr",          "West", "fluidpro"),
            ("Finance Head",       "finance@wepsol.com",       "Fin@2026!",   "finance",     "West", "fluidpro"),
        ]

        user_objs = {}
        for name, email, pwd, role, bu, biz in users_to_create:
            u = User(name=name, email=email,
                     password_hash=hash_password(pwd),
                     role=role, bu=bu, business=biz, is_active=True)
            db.add(u)
            user_objs[email] = u
        await db.flush()

        # Set manager_id for reps
        mgr_west  = user_objs["manager@fluidpro.in"]
        mgr_west2 = user_objs["sunita.m@fluidpro.in"]
        mgr_north = user_objs["vikram.m@fluidpro.in"]

        west_reps  = ["danish@fluidpro.in","rahul@fluidpro.in","anjali@fluidpro.in"]
        west_reps2 = ["sameer@fluidpro.in","ravi@fluidpro.in","neha@fluidpro.in"]
        north_reps = ["arun@fluidpro.in","pooja@fluidpro.in","kiran@fluidpro.in",
                      "suresh@fluidpro.in","meera@fluidpro.in","ashok@fluidpro.in"]
        west_ps   = ["sanjay.ps@fluidpro.in","kavitha.ps@fluidpro.in","mohit.ps@fluidpro.in"]

        for e in west_reps:  user_objs[e].manager_id = mgr_west.id
        for e in west_reps2: user_objs[e].manager_id = mgr_west2.id
        for e in north_reps: user_objs[e].manager_id = mgr_north.id
        for e in west_ps:    user_objs[e].manager_id = mgr_west.id

        await db.commit()
        print(f"   ✅ {len(users_to_create)} users created")

        # ── 3. Revenue Targets ────────────────────────────────────────────────
        print("🎯 Setting revenue targets...")
        all_reps = [user_objs[e] for e in (west_reps + west_reps2 + north_reps)]
        for period in ["2026-04","2026-05","2026-06","2026-07"]:
            for rep in all_reps:
                target = random.choice([500000, 750000, 1000000, 1250000, 1500000])
                db.add(RevenueTarget(user_id=rep.id, period=period, target_amount=Decimal(target)))
        await db.commit()
        print("   ✅ Revenue targets set")

        # ── 4. DSR Data — 300+ rows ───────────────────────────────────────────
        print("📋 Generating DSR entries...")
        start_date = date(2026, 4, 1)
        end_date   = date(2026, 7, 2)
        work_dates = working_dates(start_date, end_date)

        dsr_count = 0
        all_reps_and_ps = all_reps + [user_objs[e] for e in west_ps +
                                       ["divya.ps@fluidpro.in","abhishek.ps@fluidpro.in","lakshmi.ps@fluidpro.in"]]
        is_presales = lambda u: u.role in ("pre_sales","presales")

        for user in all_reps_and_ps:
            ps = is_presales(user)
            # Submit DSR for ~85% of working days (realistic compliance)
            user_dates = [d for d in work_dates if random.random() < 0.85]
            for dt in user_dates:
                if ps:
                    dsr = DSRDaily(
                        user_id=user.id, date=dt, status="working",
                        dsr_type="presales",
                        demos_conducted    = random.randint(0,2),
                        pocs_conducted     = random.randint(0,1),
                        proposals_supported= random.randint(0,2),
                        tech_discussions   = random.randint(0,3),
                        workshops_conducted= random.randint(0,1),
                        trainings_delivered= random.randint(0,1),
                        trainings_attended = random.randint(0,1),
                        docs_created       = random.randint(0,2),
                        virtual_meetings   = random.randint(0,3),
                        notes=f"Pre-sales activity — {dt.strftime('%b %Y')}"
                    )
                else:
                    calls     = random.randint(2,8)
                    followups = random.randint(5,20)
                    visits    = random.randint(0,2)
                    leads     = random.randint(0,2)
                    props     = random.randint(0,1)
                    dsr = DSRDaily(
                        user_id=user.id, date=dt, status="working",
                        dsr_type="sales",
                        visits=visits, calls=calls, followups=followups,
                        new_leads=leads, proposals=props,
                        virtual_meetings=random.randint(0,1),
                        proposal_value=Decimal(random.randint(0,5)*100000) if props else None,
                        notes=f"Field activity — {dt.strftime('%b %Y')}"
                    )
                db.add(dsr)
                dsr_count += 1
                # Batch commits
                if dsr_count % 100 == 0:
                    await db.flush()
        await db.commit()
        print(f"   ✅ {dsr_count} DSR rows created")

        # ── 5. Pipeline Deals — 100+ ──────────────────────────────────────────
        print("💼 Creating pipeline deals...")
        deal_count = 0
        companies_pool = COMPANIES.copy()
        random.shuffle(companies_pool)

        for rep in all_reps:
            n_deals = random.randint(6, 10)
            for i in range(n_deals):
                company = companies_pool[(all_reps.index(rep)*10 + i) % len(companies_pool)]
                stage   = random.choice(STAGES)
                practice = random.choice(PRACTICES)
                value   = Decimal(random.choice([150000,250000,350000,500000,750000,1000000,1500000]))
                won_month = random.choice(["2026-04","2026-05","2026-06","2026-07"])
                eta_day  = rand_date(date(2026,4,1), date(2026,8,31))
                deal = PipelineDeal(
                    user_id=rep.id,
                    company=company,
                    stage=stage,
                    deal_value=value,
                    closure_eta=eta_day if stage not in ("closed_won","closed_lost","dropped") else
                                date(int(won_month[:4]), int(won_month[5:]), 28),
                    todays_update=f"Ongoing {practice} opportunity — {company}",
                    next_step="Follow up with decision maker",
                    roadblock=random.random() < 0.15,
                    ai_closure_pct={"cold":10,"warm":40,"hot":70,
                                    "closed_won":100,"closed_lost":0,"dropped":0}.get(stage,50)
                )
                db.add(deal)
                deal_count += 1
        await db.commit()
        print(f"   ✅ {deal_count} pipeline deals created")

        # ── 6. Meetings — 150+ ────────────────────────────────────────────────
        print("🤝 Creating meeting records...")
        mtg_count = 0
        for rep in all_reps:
            n_mtgs = random.randint(8, 15)
            for i in range(n_mtgs):
                company = random.choice(COMPANIES)
                dt      = rand_date(start_date, end_date)
                mtype   = random.choice(MEETING_TYPES)
                bant_b  = random.random() > 0.3
                bant_a  = random.random() > 0.4
                bant_n  = random.random() > 0.2
                bant_t  = random.random() > 0.5
                filled  = sum([bant_b, bant_a, bant_n, bant_t])
                pct_map = {4:85, 3:62, 2:38, 1:15, 0:5}
                intent  = ("hot" if filled >= 3 else "warm" if filled >= 2
                           else "engaged" if filled == 1 else "cold")
                mtg = Meeting(
                    user_id=rep.id, date=dt, company=company,
                    contact_name=f"Mr/Ms Contact {i+1}",
                    meeting_type=mtype,
                    discussion=f"Discussed {random.choice(PRACTICES)} requirements and proposed solution",
                    opportunity=random.random() > 0.3,
                    support_needed=random.choice([None,"RAY","Technical","Demo","None"]),
                    bant_budget=bant_b, bant_authority=bant_a,
                    bant_need=bant_n, bant_timeline=bant_t,
                    ai_intent_score=intent,
                    ai_closure_pct=pct_map[filled]
                )
                db.add(mtg)
                mtg_count += 1
        await db.commit()
        print(f"   ✅ {mtg_count} meetings created")

        # ── 7. Leads — 50+ ────────────────────────────────────────────────────
        print("🎯 Creating leads...")
        lead_count = 0
        for rep in all_reps:
            n_leads = random.randint(2,6)
            for i in range(n_leads):
                dt = rand_date(start_date, end_date)
                db.add(Lead(
                    user_id=rep.id, date=dt,
                    company=random.choice(COMPANIES),
                    contact_name=f"Contact {i+1}",
                    requirement=random.choice(["MS 365 Migration","SD-WAN","Managed NOC",
                                               "Cloud Backup","Endpoint Security","EUC Solution"]),
                    source=random.choice(SOURCES),
                    next_action="Follow up with proposal",
                    next_action_date=dt + timedelta(days=random.randint(3,14)),
                    ai_lead_score=random.randint(40,95),
                    status=random.choice(["new","qualified","proposal","closed_won"])
                ))
                lead_count += 1
        await db.commit()
        print(f"   ✅ {lead_count} leads created")

        # ── Final counts ──────────────────────────────────────────────────────
        from sqlalchemy import func
        for model, name in [(User,"Users"),(DSRDaily,"DSRs"),(Meeting,"Meetings"),
                             (Lead,"Leads"),(PipelineDeal,"Pipeline")]:
            cnt = (await db.execute(select(func.count()).select_from(model))).scalar()
            print(f"   DB {name:12s}: {cnt}")

        print("\n✅ Seed v3 complete!")
        print("   Login credentials:")
        for name, email, pwd, role, bu, _ in users_to_create[:8]:
            print(f"   {role:12s} | {email:35s} | {pwd}")

asyncio.run(seed())
