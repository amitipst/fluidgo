"""
fluidGo seed script — populates DB with users and Danish Sayyed May 2026 DSR data.
Run: python seed.py  (from backend/ directory, with DATABASE_URL set)
"""
import asyncio
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import User, DSRDaily, SelfScore, Meeting, Lead, PipelineDeal, Base
from app.services.auth_service import hash_password
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)

USERS = [
    {"name": "Danish Sayyed",  "email": "danish@fluidpro.in",   "password": "Fluid@2026!", "role": "rep",           "bu": "West"},
    {"name": "Amit Singh",     "email": "amit@wepsol.com",       "password": "Admin@2026!", "role": "bu_head",        "bu": "West"},
    {"name": "Team Manager",   "email": "manager@fluidpro.in",   "password": "Mgr@2026!",   "role": "manager",        "bu": "West"},
    {"name": "Inside Sales",   "email": "inside@fluidpro.in",    "password": "Inside@2026!","role": "inside_sales",   "bu": "West"},
]

# Danish's May 2026 data (from actual DSR excel)
DSR_ROWS = [
    (date(2026,5,4),  "working", 1,0,5,0,10,0,"Nido legal docs"),
    (date(2026,5,5),  "working", 2,0,0,2,5,0, "Eagle SPS visit, New leads added"),
    (date(2026,5,6),  "leave",   0,0,0,0,0,0,  "On Leave"),
    (date(2026,5,7),  "working", 0,0,3,0,10,0, "Follow-ups only"),
    (date(2026,5,8),  "working", 1,0,0,0,10,0, "Nido closure discussion"),
    (date(2026,5,11), "working", 0,0,3,0,10,1, "Proposal to Vakksh Capital"),
    (date(2026,5,12), "working", 1,0,3,0,12,0, "MRR hospital — no req"),
    (date(2026,5,13), "working", 1,0,5,0,5,0,  "New Era Cleantech — proposal"),
    (date(2026,5,14), "working", 0,0,5,0,15,0, "Intensive follow-ups"),
    (date(2026,5,15), "working", 0,0,5,0,10,1, "Proposal sent"),
    (date(2026,5,18), "working", 1,0,4,0,12,0, "Nido — extended to next month"),
    (date(2026,5,19), "working", 0,0,6,0,24,0, "High follow-up day"),
    (date(2026,5,20), "working", 0,0,0,0,0,0,  "No activity logged"),
]

MEETINGS = [
    ("Nido Home Finance Ltd",                date(2026,5,4),  "F2F",  "Discussed legal documents with legal team", True, "RAY", True,True,True,True),
    ("Eagle SPS India Pvt Ltd",              date(2026,5,5),  "F2F",  "IT person not joined. Wait till next week", True, None,  False,False,True,False),
    ("Vakksh Capital Co Ltd",                date(2026,5,5),  "F2F",  "Commercial proposal discussed, revised cost indicated",True,"RAY",True,True,True,False),
    ("Nido Home Finance Ltd",                date(2026,5,8),  "F2F",  "Closure discussion, next level meeting next week",True,"RAY",True,True,True,True),
    ("MRR Children's Hospital",              date(2026,5,12), "F2F",  "No requirement currently",               False,None, False,False,False,False),
    ("New Era Cleantech Solutions Pvt Ltd",  date(2026,5,13), "F2F",  "Proposal for MS Business Basic and email migration",True,None,True,True,True,False),
    ("Nido Home Finance Ltd",                date(2026,5,18), "F2F",  "Requirement extended to next month",     True, "RAY",True,True,True,False),
]

LEADS = [
    ("Autosys Industrial Solutions Pvt Ltd", date(2026,5,5), "Mr Eishan",   "MS Licences",     "Call", "Shared Crayon pricing",         date(2026,5,7)),
    ("New Era Cleantech Solution Pvt Ltd",   date(2026,5,5), "Ms Ujjawala", "Cloud Migration", "Call", "Discuss details — she was busy", date(2026,5,8)),
]

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        # Create users
        danish_id = None
        for u in USERS:
            from sqlalchemy import select
            existing = (await db.execute(
                select(User).where(User.email == u["email"])
            )).scalar_one_or_none()
            if not existing:
                user = User(name=u["name"], email=u["email"],
                            password_hash=hash_password(u["password"]),
                            role=u["role"], bu=u["bu"])
                db.add(user)
                await db.flush()
                if u["email"] == "danish@fluidpro.in":
                    danish_id = user.id
            else:
                if existing.email == "danish@fluidpro.in":
                    danish_id = existing.id

        await db.commit()

        if not danish_id:
            from sqlalchemy import select
            danish_id = (await db.execute(
                select(User.id).where(User.email == "danish@fluidpro.in")
            )).scalar_one()

        # DSR rows
        for row in DSR_ROWS:
            d, status, vis, virt, calls, leads, fu, prop, notes = row
            from sqlalchemy import select, and_
            ex = (await db.execute(
                select(DSRDaily).where(and_(DSRDaily.user_id == danish_id, DSRDaily.date == d))
            )).scalar_one_or_none()
            if not ex:
                dsr = DSRDaily(user_id=danish_id, date=d, status=status, visits=vis,
                               virtual_meetings=virt, calls=calls, new_leads=leads,
                               followups=fu, proposals=prop, notes=notes)
                db.add(dsr)

        # Meetings
        for company, dt, mtype, disc, opp, support, bb, ba, bn, bt in MEETINGS:
            meet = Meeting(user_id=danish_id, date=dt, company=company,
                           meeting_type=mtype, discussion=disc, opportunity=opp,
                           support_needed=support, bant_budget=bb, bant_authority=ba,
                           bant_need=bn, bant_timeline=bt)
            from app.services.rigor_service import bant_score
            bs = bant_score(meet)
            meet.ai_intent_score = bs["intent"]
            meet.ai_closure_pct = bs["closure_pct"]
            db.add(meet)

        # Leads
        from app.services.rigor_service import score_lead
        for company, dt, contact, req, source, action, eta in LEADS:
            lead = Lead(user_id=danish_id, date=dt, company=company,
                        contact_name=contact, requirement=req, source=source,
                        next_action=action, next_action_date=eta)
            lead.ai_lead_score = score_lead(lead)
            db.add(lead)

        await db.commit()
        print("✅ Seed complete — users, DSR, meetings, and leads loaded.")

if __name__ == "__main__":
    asyncio.run(seed())
