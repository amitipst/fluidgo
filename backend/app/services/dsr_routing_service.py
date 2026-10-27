"""DSR routing (v1.6.3): a submitted DSR reaches the reporting manager, and optionally the BU head.

Amit (27 Oct 2026): "DSR should go to reporting manager along with BU head ... history as per role
hierarchy". Visibility and approval already follow the reporting chain (manager subtree, region,
business). What was missing was the push: nobody was told a DSR was waiting.

Best-practice default: the direct reporting manager is emailed on each new submission and on a
resubmission after rejection (not on every small edit). The business head sees the DSR in Team
Approval and history; copying the business head on every email is OFF by default (a large team
would flood the inbox) and is switched on in feature_flags key `dsr_routing`:
    {"notify_manager": true, "cc_business_head": true}
The email degrades to a server log when SMTP is not configured, like every other notice.
"""
from __future__ import annotations

from html import escape
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

FLAG_KEY = "dsr_routing"
DEFAULTS = {"notify_manager": True, "cc_business_head": False}


def should_notify(is_update: bool, prev_status: Optional[str]) -> bool:
    """New submission, or a resubmission after the manager rejected it."""
    return (not is_update) or prev_status == "rejected"


async def get_config(db: AsyncSession) -> dict:
    from app.services.lead_stage_service import get_feature_flag
    cfg = dict(DEFAULTS)
    flag = await get_feature_flag(db, FLAG_KEY)
    if flag and flag.enabled and flag.config:
        for k in DEFAULTS:
            if isinstance(flag.config.get(k), bool):
                cfg[k] = flag.config[k]
    return cfg


async def resolve_recipients(db: AsyncSession, user, cfg: dict) -> tuple[list[str], list[str]]:
    """(to, cc) email lists. Direct manager first; business head(s) in cc when enabled."""
    to: list[str] = []
    cc: list[str] = []
    if cfg.get("notify_manager") and getattr(user, "manager_id", None):
        mgr = (await db.execute(select(User).where(User.id == user.manager_id, User.is_active == True))).scalar_one_or_none()  # noqa: E712
        if mgr and mgr.email:
            to.append(mgr.email)
    if cfg.get("cc_business_head"):
        heads = (await db.execute(select(User.email).where(
            User.role.in_(["business_head", "practice_head"]), User.is_active == True,  # noqa: E712
            User.business == user.business))).scalars().all()
        for e in heads:
            if e and e not in to and e != user.email:
                cc.append(e)
        if not to and cc:          # no reporting manager bound: the business head becomes the recipient
            to, cc = cc, []
    return to, cc


def build_notice(user_name: str, dsr_date, rigor: int, resubmitted: bool) -> tuple[str, str, str]:
    verb = "resubmitted" if resubmitted else "submitted"
    subject = f"DSR {verb}: {user_name} — {dsr_date}"
    text = f"{user_name} {verb} the DSR for {dsr_date} (rigor {rigor}). Review it in fluidGo → DSR History → Team Approval."
    html = (f"<p><b>{escape(user_name)}</b> {verb} the DSR for <b>{escape(str(dsr_date))}</b> "
            f"(rigor {rigor}).</p><p>Review it in fluidGo → DSR History → Team Approval.</p>")
    return subject, html, text
