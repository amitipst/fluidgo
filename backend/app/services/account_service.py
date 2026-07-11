"""CSG Phase 1 — account identity resolution. A thin helper, not a full
account-management module (no dedupe UI, no merge workflow yet — Phase 3).
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Account


async def get_or_create_account(
    db: AsyncSession, name: str, business: str = "fluidpro", region: str | None = None
) -> Account:
    """Case-insensitive lookup by (name, business); creates one if none
    matches. Does NOT commit — caller's transaction controls that, so this
    can be composed into a larger save (e.g. flagging an opportunity)
    without an intermediate commit splitting the operation."""
    name_clean = name.strip()
    existing = (await db.execute(
        select(Account).where(
            func.lower(Account.name) == name_clean.lower(),
            Account.business == business,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    account = Account(name=name_clean, business=business, region=region)
    db.add(account)
    await db.flush()
    return account
