"""Company -> contact linking for leads and deals (v1.5.0, 2026-10-26).

Amit: "once a contact company is added, it should be connected to leads,
deals, pipeline etc, any new lead, deal should start with contact creation if
not already present, and 2 or 3 deals can run in a single customer."

Before this, `Lead.company` / `PipelineDeal.company` were free text, so the
same customer appeared under three spellings (Sunpack Group / Systems /
Solutions Pvt Ltd) and the Contacts master showed 2 companies with 0 people
while 30+ deals existed. Now a lead or deal is created *against* an Account and
a Contact. The old text columns are kept and filled from the master
(`company` = account name, `contact_name` / `primary_contact` = person) so every
existing screen, export and report keeps working untouched — extend, not
rebuild.

Many deals per company is simply many PipelineDeal rows sharing an
`account_id`; nothing here (or anywhere) enforces one-deal-per-account.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Contact
from app.services.contact_service import full_name
from app.services.deal_rules_service import RuleViolation


async def resolve_links(db: AsyncSession, account_id: Optional[uuid.UUID],
                        contact_id: Optional[uuid.UUID], require: bool
                        ) -> tuple[Optional[Account], Optional[Contact]]:
    """Validate and load the company/contact pair.

    require=True (the default business rule): both must be given. Otherwise a
    pair is optional, but if either is given it must be valid and the contact
    must belong to the company — a deal can never point at company A with a
    person from company B.
    """
    if account_id is None and contact_id is None:
        if require:
            raise RuleViolation(
                "Pick the company and the contact first. If they are not in the "
                "system yet, add them — it takes a minute and links everything.")
        return None, None
    if account_id is None:
        raise RuleViolation("Pick the company for this contact.")

    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if account is None:
        raise RuleViolation("That company no longer exists. Pick or add it again.")

    if contact_id is None:
        if require:
            raise RuleViolation(f"Pick or add a contact at {account.name}.")
        return account, None

    contact = (await db.execute(select(Contact).where(Contact.id == contact_id))).scalar_one_or_none()
    if contact is None or contact.deleted_at is not None:
        raise RuleViolation("That contact no longer exists. Pick or add them again.")
    if contact.account_id != account.id:
        raise RuleViolation(f"{full_name(contact.first_name, contact.last_name)} does not belong to {account.name}.")
    if contact.status == "left":
        raise RuleViolation(
            f"{full_name(contact.first_name, contact.last_name)} has left {account.name}. "
            "Pick a current contact, or add the new person.")
    return account, contact


def display_name(contact: Optional[Contact]) -> Optional[str]:
    return full_name(contact.first_name, contact.last_name) if contact else None
