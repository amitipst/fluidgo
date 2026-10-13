"""In-app feedback / issue capture.

Any logged-in user (any role) can file feedback from anywhere in the app —
a bug, an idea, a question, or something else. Two things happen every
time, unconditionally:
  1. The row is saved to `feedback` — this table is always the system of
     record, regardless of whether Jira is configured.
  2. super_admin/ceo get an email alert (background task, reuses the
     existing SMTP config) — so an admin "can't miss it" per the original
     ask, without needing to remember to check an inbox page.

Filing a matching Jira issue is a bonus layered on top when JIRA_* settings
are present (see app.config.jira_configured / app.services.jira_service).
If Jira isn't configured, or the call fails, feedback is still saved and
still alerts — jira_sync_error records why, and an admin can retry later.
No separate issue tracker is required to get started.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional, Literal
import uuid

from app.database import get_db, AsyncSessionLocal
from app.models import Feedback, User, role_level
from app.services.deps import get_current_user
from app.services.email_service import send_email
from app.services import jira_service

router = APIRouter()

ADMIN_ALERT_ROLES = ("super_admin", "ceo")
# Business_head+ can triage the inbox — matches the threshold used elsewhere
# for seed-data visibility etc. (app.models.role_level).
REVIEW_LEVEL = 40


class FeedbackIn(BaseModel):
    category: Literal["bug", "idea", "question", "other"] = "other"
    message: str
    page_context: Optional[str] = None


def _serialize(f: Feedback, reporter_name: str = "", reporter_email: str = "") -> dict:
    return {
        "id": str(f.id),
        "user_id": str(f.user_id),
        "reporter_name": reporter_name,
        "reporter_email": reporter_email,
        "role": f.role,
        "category": f.category,
        "message": f.message,
        "page_context": f.page_context,
        "status": f.status,
        "jira_issue_key": f.jira_issue_key,
        "jira_issue_url": f.jira_issue_url,
        "jira_sync_error": f.jira_sync_error,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None,
    }


async def _file_jira_and_alert(feedback_id: str, reporter_name: str, reporter_email: str, reporter_role: str):
    """Runs after the response has already gone back to the user — files the
    Jira issue (if configured) and emails super_admin/ceo. Uses its own DB
    session since this fires from a BackgroundTasks callback."""
    async with AsyncSessionLocal() as db:
        fb = (await db.execute(select(Feedback).where(Feedback.id == uuid.UUID(feedback_id)))).scalar_one_or_none()
        if not fb:
            return

        jira_result = None
        try:
            summary = f"[fluidGo] {fb.category}: {fb.message[:80]}"
            jira_result = await jira_service.create_issue(
                summary=summary,
                description=f"Category: {fb.category}\nReported from: {fb.page_context or 'unknown page'}\n\n{fb.message}",
                reporter_email=reporter_email,
                category=fb.category,
            )
        except Exception as e:
            fb.jira_sync_error = str(e)

        if jira_result:
            fb.jira_issue_key = jira_result["key"]
            fb.jira_issue_url = jira_result["url"]
        elif not fb.jira_sync_error:
            # jira_configured was False — not an error, just not set up yet
            fb.jira_sync_error = None

        await db.commit()

        # Alert admins — always, regardless of Jira outcome
        admins = (await db.execute(
            select(User).where(User.role.in_(ADMIN_ALERT_ROLES), User.is_active == True)
        )).scalars().all()

        jira_line = (
            f'<p>Filed in Jira: <a href="{jira_result["url"]}">{jira_result["key"]}</a></p>'
            if jira_result else
            '<p style="color:#999">Not filed in Jira (not configured, or filing failed — check the Feedback inbox).</p>'
        )
        subject = f"[fluidGo Feedback] {fb.category.upper()} from {reporter_name}"
        html_body = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;color:#1A0B2E">
  <div style="background:linear-gradient(135deg,#F0115E,#92278E);padding:16px 20px;border-radius:12px 12px 0 0">
    <div style="color:#fff;font-size:16px;font-weight:700">New fluidGo Feedback</div>
  </div>
  <div style="border:1px solid #eee;border-top:none;padding:20px;border-radius:0 0 12px 12px">
    <p><strong>{reporter_name}</strong> ({reporter_role}) reported a <strong>{fb.category}</strong>
       from <em>{fb.page_context or 'unknown page'}</em>:</p>
    <p style="background:#F7F3FC;border-radius:8px;padding:12px;white-space:pre-wrap">{fb.message}</p>
    {jira_line}
    <p style="color:#999;font-size:12px;margin-top:16px">
      Reported {fb.created_at.strftime('%d %b %Y, %H:%M')} · Review it in fluidGo → Feedback inbox.
    </p>
  </div>
</div>"""
        text_body = (
            f"{reporter_name} ({reporter_role}) reported a {fb.category} from "
            f"{fb.page_context or 'unknown page'}:\n\n{fb.message}\n\n"
            + (f"Jira: {jira_result['url']}\n" if jira_result else "Not filed in Jira.\n")
        )
        for admin in admins:
            await send_email([admin.email], subject, html_body, text_body)


@router.post("")
async def submit_feedback(
    body: FeedbackIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.message.strip():
        raise HTTPException(400, "Please describe the issue or idea before submitting.")

    fb = Feedback(
        user_id=user.id,
        role=user.role,
        category=body.category,
        message=body.message.strip(),
        page_context=body.page_context,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    background_tasks.add_task(_file_jira_and_alert, str(fb.id), user.name, user.email, user.role)

    return {"message": "Thanks — your feedback was received and the team's been notified.",
            "id": str(fb.id)}


@router.get("")
async def list_feedback(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if role_level(user.role) < REVIEW_LEVEL:
        raise HTTPException(403, "Not authorised to view the feedback inbox")

    q = select(Feedback).order_by(Feedback.created_at.desc())
    if status:
        q = q.where(Feedback.status == status)
    items = (await db.execute(q)).scalars().all()

    user_ids = {f.user_id for f in items}
    reporters = {}
    if user_ids:
        users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        reporters = {u.id: u for u in users}

    return [
        _serialize(f, reporters.get(f.user_id).name if reporters.get(f.user_id) else "Unknown",
                   reporters.get(f.user_id).email if reporters.get(f.user_id) else "")
        for f in items
    ]


@router.get("/pending-count")
async def pending_feedback_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Powers the sidebar badge — cheap count query, polled every 60s like
    the DSR edit-request badge."""
    if role_level(user.role) < REVIEW_LEVEL:
        return {"count": 0}
    count = (await db.execute(
        select(func.count()).select_from(Feedback).where(Feedback.status == "open")
    )).scalar_one()
    return {"count": count}


class ReviewIn(BaseModel):
    status: Literal["open", "in_progress", "resolved", "wont_fix"]


@router.post("/{feedback_id}/review")
async def review_feedback(
    feedback_id: str,
    body: ReviewIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if role_level(user.role) < REVIEW_LEVEL:
        raise HTTPException(403, "Not authorised to update feedback status")

    fb = (await db.execute(select(Feedback).where(Feedback.id == uuid.UUID(feedback_id)))).scalar_one_or_none()
    if not fb:
        raise HTTPException(404, "Feedback not found")

    fb.status = body.status
    fb.reviewed_at = datetime.utcnow()
    fb.reviewed_by = user.id
    await db.commit()
    return {"message": "Updated.", "status": fb.status}
