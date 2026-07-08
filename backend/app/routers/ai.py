from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import uuid
from app.database import get_db
from app.models import AIInsight, DSRDaily, Meeting, User
from app.services.deps import get_current_user
from app.services.ai_service import analyse, stream_analyse
from app.services.rigor_service import calculate_rigor_score, bant_score

router = APIRouter()

ENTITY_PROMPT_MAP = {
    "dsr": "daily_insight", "rep": "daily_insight",
    "deal": "deal_analysis", "pipeline": "pipeline_review",
    "team": "team_analysis", "lead": "lead_scoring",
}

class AnalyseRequest(BaseModel):
    entity_type: str   # dsr | deal | team | rep | pipeline | lead
    entity_id: str | None = None
    insight_type: str | None = None   # rigor | bant | closure | gap — defaults from entity_type
    context: str

async def _cache_insight(db: AsyncSession, entity_type: str,
                          entity_id: str | None, insight_type: str, content: str):
    ins = AIInsight(
        entity_type=entity_type,
        entity_id=uuid.UUID(entity_id) if entity_id else None,
        insight_type=insight_type,
        content=content
    )
    db.add(ins)
    await db.commit()

@router.post("/analyse")
async def analyse_entity(body: AnalyseRequest, background_tasks: BackgroundTasks,
                          db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    insight_type = body.insight_type or ENTITY_PROMPT_MAP.get(body.entity_type, "gap")
    # Check cache — 6h TTL, scoped to this exact entity
    if body.entity_id:
        cutoff = datetime.utcnow() - timedelta(hours=6)
        result = await db.execute(
            select(AIInsight).where(
                AIInsight.entity_type == body.entity_type,
                AIInsight.entity_id == uuid.UUID(body.entity_id),
                AIInsight.insight_type == insight_type,
                AIInsight.generated_at > cutoff
            ).order_by(AIInsight.generated_at.desc()).limit(1)
        )
        cached = result.scalar_one_or_none()
        if cached:
            return {"content": cached.content, "cached": True}

    prompt_type = ENTITY_PROMPT_MAP.get(body.entity_type, "daily_insight")
    content = await analyse(body.context, prompt_type=prompt_type)
    background_tasks.add_task(
        _cache_insight, db, body.entity_type, body.entity_id, insight_type, content
    )
    return {"content": content, "cached": False}

@router.post("/analyse/stream")
async def analyse_stream(body: AnalyseRequest, user: User = Depends(get_current_user)):
    prompt_type = ENTITY_PROMPT_MAP.get(body.entity_type, "daily_insight")
    return StreamingResponse(
        stream_analyse(body.context, prompt_type=prompt_type),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

async def generate_dashboard_insight(user_id: str):
    """Runs in the background — never blocks an HTTP request. Builds the
    context, calls Ollama (which can legitimately take 30s-4min on this
    CPU-only host), and writes the result to ai_insights. Uses its own DB
    session since this runs after the triggering request has already
    returned (login) or independently (regenerate)."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        uid = uuid.UUID(user_id)
        try:
            result = await db.execute(
                select(DSRDaily).where(DSRDaily.user_id == uid)
                .order_by(DSRDaily.date.desc()).limit(20)
            )
            dsrs = result.scalars().all()
            meet_result = await db.execute(
                select(Meeting).where(Meeting.user_id == uid)
                .order_by(Meeting.date.desc()).limit(10)
            )
            meetings = meet_result.scalars().all()

            total_calls = sum(d.calls for d in dsrs)
            total_followups = sum(d.followups for d in dsrs)
            total_visits = sum(d.visits for d in dsrs)
            total_leads = sum(d.new_leads for d in dsrs)
            working = [d for d in dsrs if d.status == "working"]
            avg_rigor = sum(calculate_rigor_score(d) for d in working) / max(len(working), 1)

            meeting_lines = []
            for m in meetings:
                bs = bant_score(m)
                meeting_lines.append(
                    f"- {m.company} ({m.meeting_type}, {m.date}): BANT {bs['bant_filled']}/4, "
                    f"Intent={bs['intent']}, Closure={bs['closure_pct']}%, Gaps={','.join(bs['gaps']) or 'None'}"
                )

            context = f"""Sales Rep Activity (last {len(dsrs)} working days):
Total Calls: {total_calls} | Visits: {total_visits} | Follow-ups: {total_followups} | New Leads: {total_leads}
Average Rigor Score: {avg_rigor:.0f}/100

Recent Meetings and Deals:
{chr(10).join(meeting_lines) if meeting_lines else 'No meetings logged yet'}

Analyse this FluidPro field sales rep's performance. Give:
1. Rigor assessment (is the activity level sufficient?)
2. Top 2 deal priorities with specific next actions
3. Critical gaps in lead generation or pipeline
4. One honest coaching observation"""

            content = await analyse(context, prompt_type="daily_insight")
            failed = content.startswith("⚠️")  # analyse()'s own fallback prefix
        except Exception as e:
            content, failed = str(e), True

        existing = (await db.execute(
            select(AIInsight).where(
                AIInsight.entity_type == "dashboard",
                AIInsight.entity_id == uid,
            )
        )).scalar_one_or_none()

        if existing:
            existing.status = "failed" if failed else "ready"
            existing.content = content
            existing.error_detail = content if failed else None
            existing.generated_at = datetime.utcnow()
        else:
            db.add(AIInsight(
                entity_type="dashboard", entity_id=uid, insight_type="daily_insight",
                status="failed" if failed else "ready",
                content=content, error_detail=content if failed else None,
                generated_at=datetime.utcnow(),
            ))
        await db.commit()


@router.get("/dashboard/{user_id}")
async def dashboard_insights(user_id: str, background_tasks: BackgroundTasks,
                              db: AsyncSession = Depends(get_db),
                              user: User = Depends(get_current_user)):
    """Reads the CACHED insight — never generates synchronously, so this
    always responds instantly regardless of how slow the model is."""
    uid = uuid.UUID(user_id)
    existing = (await db.execute(
        select(AIInsight).where(
            AIInsight.entity_type == "dashboard",
            AIInsight.entity_id == uid,
        )
    )).scalar_one_or_none()

    if not existing:
        # Never generated before — kick it off now and tell the frontend to poll.
        background_tasks.add_task(generate_dashboard_insight, user_id)
        return {"status": "pending", "content": None, "generated_at": None}

    return {
        "status": existing.status,
        "content": existing.content,
        "generated_at": existing.generated_at.isoformat() if existing.generated_at else None,
    }


@router.post("/dashboard/{user_id}/regenerate")
async def regenerate_dashboard_insight(user_id: str, background_tasks: BackgroundTasks,
                                        db: AsyncSession = Depends(get_db),
                                        user: User = Depends(get_current_user)):
    """Manual 'Run Analysis' — marks pending immediately (so the UI can show
    a spinner right away) and kicks off generation in the background."""
    uid = uuid.UUID(user_id)
    existing = (await db.execute(
        select(AIInsight).where(
            AIInsight.entity_type == "dashboard",
            AIInsight.entity_id == uid,
        )
    )).scalar_one_or_none()
    if existing:
        existing.status = "pending"
    else:
        db.add(AIInsight(entity_type="dashboard", entity_id=uid,
                          insight_type="daily_insight", status="pending"))
    await db.commit()

    background_tasks.add_task(generate_dashboard_insight, user_id)
    return {"status": "pending"}


# ── Team analysis — same background pattern as the personal dashboard ─────────
async def generate_team_insight(manager_id: str):
    """Background team analysis for a manager, keyed by their user_id with
    entity_type='team'. Builds context from their visible team's DSR activity."""
    from app.database import AsyncSessionLocal
    from app.services.permission_service import resolve_visible_user_ids
    from app.services.rigor_service import calculate_rigor_score
    from datetime import date
    async with AsyncSessionLocal() as db:
        mid = uuid.UUID(manager_id)
        try:
            manager = (await db.execute(select(User).where(User.id == mid))).scalar_one_or_none()
            visible = await resolve_visible_user_ids(db, manager) if manager else None
            q = select(User).where(User.is_active == True,
                                   User.role.in_(["rep", "inside_sales", "pre_sales", "manager"]))
            if visible is not None:
                q = q.where(User.id.in_(visible))
            team = (await db.execute(q)).scalars().all()

            lines = []
            for u in team:
                dsrs = (await db.execute(
                    select(DSRDaily).where(DSRDaily.user_id == u.id)
                    .order_by(DSRDaily.date.desc()).limit(20)
                )).scalars().all()
                working = [d for d in dsrs if d.status == "working"]
                rigor = sum(calculate_rigor_score(d) for d in working) / max(len(working), 1)
                lines.append(
                    f"{u.name} ({u.role}): Rigor={rigor:.0f}, "
                    f"Calls={sum(d.calls for d in dsrs)}, Visits={sum(d.visits for d in dsrs)}, "
                    f"Leads={sum(d.new_leads for d in dsrs)}, Proposals={sum(d.proposals for d in dsrs)}, "
                    f"WorkingDays={len(working)}"
                )

            context = (
                f"Team Performance (last 20 working days):\n" + "\n".join(lines) +
                "\n\nProvide: 1) Team pulse (overall health), 2) Strong performers, "
                "3) Who needs attention and why, 4) One concrete coaching recommendation."
            )
            content = await analyse(context, prompt_type="team_analysis")
            failed = content.startswith("⚠️")
        except Exception as e:
            content, failed = str(e), True

        existing = (await db.execute(
            select(AIInsight).where(
                AIInsight.entity_type == "team", AIInsight.entity_id == mid,
            )
        )).scalar_one_or_none()
        if existing:
            existing.status = "failed" if failed else "ready"
            existing.content = content
            existing.error_detail = content if failed else None
            existing.generated_at = datetime.utcnow()
        else:
            db.add(AIInsight(entity_type="team", entity_id=mid, insight_type="team_analysis",
                             status="failed" if failed else "ready",
                             content=content, error_detail=content if failed else None,
                             generated_at=datetime.utcnow()))
        await db.commit()


@router.get("/team/{manager_id}")
async def team_insight(manager_id: str, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Reads the cached team insight instantly; kicks off generation if none exists."""
    mid = uuid.UUID(manager_id)
    existing = (await db.execute(
        select(AIInsight).where(AIInsight.entity_type == "team", AIInsight.entity_id == mid)
    )).scalar_one_or_none()
    if not existing:
        background_tasks.add_task(generate_team_insight, manager_id)
        return {"status": "pending", "content": None, "generated_at": None}
    return {
        "status": existing.status,
        "content": existing.content,
        "generated_at": existing.generated_at.isoformat() if existing.generated_at else None,
    }


@router.post("/team/{manager_id}/regenerate")
async def regenerate_team_insight(manager_id: str, background_tasks: BackgroundTasks,
                                   db: AsyncSession = Depends(get_db),
                                   user: User = Depends(get_current_user)):
    mid = uuid.UUID(manager_id)
    existing = (await db.execute(
        select(AIInsight).where(AIInsight.entity_type == "team", AIInsight.entity_id == mid)
    )).scalar_one_or_none()
    if existing:
        existing.status = "pending"
    else:
        db.add(AIInsight(entity_type="team", entity_id=mid,
                          insight_type="team_analysis", status="pending"))
    await db.commit()
    background_tasks.add_task(generate_team_insight, manager_id)
    return {"status": "pending"}
