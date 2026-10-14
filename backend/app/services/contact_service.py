"""Contacts master — business rules (v1.4.0-A).

Pure helpers (phone normalisation, name split, duplicate keys, approval state
machine) are kept free of DB access so they can be unit-tested directly; the
async helpers below them are thin queries. Extends, does not replace:
accounts still come from account_service.get_or_create_account(); visibility
still comes from permission_service.resolve_visible_user_ids().

Rules implemented (decisions 2026-10-13 / 2026-10-14, design doc §9, §9a, §9b):
  * primary phone is REQUIRED for every new or edited contact (API-level;
    legacy backfilled rows are flagged `incomplete` and must be completed
    before they can be added to a MOM).
  * duplicates within an account (same normalised primary phone, same
    lower-cased email, or same full name) are offered back as "use existing";
    creating anyway needs a written reason.
  * nobody hard-deletes: a delete REQUEST needs the requester's reporting
    manager AND one of governance / inside sales; any rejection stops it;
    pending requests expire after 14 days; final approval soft-deletes.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Iterable

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Contact

DELETE_REQUEST_TTL_DAYS = 14
# hr and finance have no account work, and contacts are customer personal data
# (DPDP Act): least privilege means they get nothing. Governance reads
# everything but writes nothing (restore is its one explicit exception).
NO_CONTACT_ACCESS_ROLES = {"hr", "finance"}
READ_ONLY_ROLES = {"governance"}
RESTORE_ROLES = {"governance", "super_admin", "business_head", "practice_head", "coo", "ceo"}


# ── pure helpers ────────────────────────────────────────────────────────────
def normalize_phone(raw: Optional[str], default_cc: str = "+91") -> Optional[str]:
    """Return a canonical phone string, or None if it is not a plausible number.

    10-digit Indian mobiles (start 6-9) and 0-prefixed 11-digit numbers get
    +91; anything starting with + or 00 keeps its own country code. Digits only
    otherwise; 8-15 digits overall."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    has_plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if s.startswith("00") and not has_plus:
        has_plus, digits = True, digits[2:]
    if has_plus:
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    if len(digits) == 10 and digits[0] in "6789":
        return f"{default_cc}{digits}"
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return f"{default_cc}{digits[1:]}"
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+{digits}"
    if 8 <= len(digits) <= 15 and not digits.startswith("0"):
        # landline / other formats typed without a country code: keep digits
        return f"{default_cc}{digits}" if len(digits) <= 11 else f"+{digits}"
    return None


def split_name(full: str) -> tuple[str, Optional[str]]:
    parts = " ".join((full or "").split()).split(" ")
    first = parts[0] if parts and parts[0] else ""
    last = " ".join(parts[1:]) or None
    return first, last


def full_name(first: str, last: Optional[str]) -> str:
    return " ".join(p for p in [first, last] if p).strip()


def duplicate_reasons(candidate: dict, existing: dict) -> list[str]:
    """Why `existing` looks like the same person as `candidate` (both plain
    dicts with first_name/last_name/email/phone_primary). Empty list = no."""
    reasons = []
    cp, ep = candidate.get("phone_primary"), existing.get("phone_primary")
    if cp and ep and cp == ep:
        reasons.append("same primary number")
    ce, ee = (candidate.get("email") or "").lower(), (existing.get("email") or "").lower()
    if ce and ee and ce == ee:
        reasons.append("same email")
    cn = full_name(candidate.get("first_name", ""), candidate.get("last_name")).lower()
    en = full_name(existing.get("first_name", ""), existing.get("last_name")).lower()
    if cn and cn == en:
        reasons.append("same name")
    return reasons


def decide_state(approvals: Iterable[dict]) -> str:
    """Delete-request state from the recorded approvals.

    'rejected' if anyone rejected; 'approved' once the reporting manager AND
    one of governance / inside sales have approved; else 'pending'."""
    approvals = list(approvals)
    if any(a["decision"] == "reject" for a in approvals):
        return "rejected"
    slots = {a["approver_slot"] for a in approvals if a["decision"] == "approve"}
    if "manager" in slots and slots & {"governance", "inside_sales"}:
        return "approved"
    return "pending"


def approver_slot(approver, requester, existing_slots: set[str]) -> Optional[str]:
    """Which approval slot `approver` may fill for a request by `requester`,
    or None if they may not decide it at all."""
    if approver.id == requester.id:
        return None                                   # never approve your own request
    if requester.manager_id is not None and approver.id == requester.manager_id:
        return "manager"
    if approver.role == "governance":
        return "governance"
    if approver.role == "inside_sales":
        return "inside_sales"
    if requester.manager_id is None and approver.role in ("business_head", "practice_head"):
        return "manager"                              # requester has no manager: a business head stands in
    if approver.role == "super_admin":
        return "manager" if "manager" not in existing_slots else "governance"
    return None


def can_complete_contact(contact) -> bool:
    """A contact can be added to a MOM only with a primary number on file."""
    return bool(getattr(contact, "phone_primary", None)) and not getattr(contact, "incomplete", False)


# ── async helpers ───────────────────────────────────────────────────────────
def serialize(c: Contact, account_name: Optional[str] = None) -> dict:
    return {
        "id": str(c.id), "account_id": str(c.account_id), "account_name": account_name,
        "salutation": c.salutation, "first_name": c.first_name, "last_name": c.last_name,
        "name": full_name(c.first_name, c.last_name),
        "designation": c.designation, "department": c.department,
        "email": c.email, "phone_primary": c.phone_primary, "phone_secondary": c.phone_secondary,
        "linkedin_url": c.linkedin_url, "reports_to_contact_id": str(c.reports_to_contact_id) if c.reports_to_contact_id else None,
        "is_primary_contact": bool(c.is_primary_contact), "status": c.status,
        "do_not_contact": bool(c.do_not_contact), "incomplete": bool(c.incomplete) or not c.phone_primary,
        "owner_user_id": str(c.owner_user_id) if c.owner_user_id else None,
        "created_by": str(c.created_by) if c.created_by else None,
        "last_activity_at": c.last_activity_at.isoformat() if c.last_activity_at else None,
        "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


async def find_duplicates(db: AsyncSession, account_id, candidate: dict,
                          exclude_id=None) -> list[dict]:
    q = select(Contact).where(Contact.account_id == account_id, Contact.deleted_at.is_(None))
    if exclude_id:
        q = q.where(Contact.id != exclude_id)
    out = []
    for c in (await db.execute(q)).scalars().all():
        why = duplicate_reasons(candidate, {
            "first_name": c.first_name, "last_name": c.last_name,
            "email": c.email, "phone_primary": c.phone_primary})
        if why:
            out.append({**serialize(c), "match_reasons": why})
    return out


def visibility_filter(visible_ids: Optional[list], user_id):
    """SQL condition limiting Contact (joined to Account) to what a user may
    see. `visible_ids is None` means unrestricted (CEO/COO/super_admin/
    governance). Otherwise: contacts the user or their reports created or own,
    on accounts they or their reports own, plus unowned accounts (any
    sales-family user may work an account nobody owns yet, so SPANCO can start)."""
    if visible_ids is None:
        return None
    ids = list(visible_ids) + [user_id]
    return or_(Contact.created_by.in_(ids), Contact.owner_user_id.in_(ids),
               Account.primary_owner_id.in_(ids), Account.primary_owner_id.is_(None))


async def touch_contacts(db: AsyncSession, attendees: Optional[list], account_id) -> None:
    """Stamp last_activity_at on every contact referenced by a MOM's attendees
    (feeds stale-contact flags later). Ignores entries without a contact_id."""
    ids = []
    for a in attendees or []:
        cid = a.get("contact_id") if isinstance(a, dict) else None
        if cid:
            try:
                ids.append(uuid.UUID(str(cid)))
            except ValueError:
                pass
    if not ids:
        return
    now = datetime.now(timezone.utc)
    for c in (await db.execute(select(Contact).where(Contact.id.in_(ids)))).scalars().all():
        c.last_activity_at = now


async def validate_attendee_contacts(db: AsyncSession, attendees: Optional[list], account_id) -> Optional[str]:
    """Return an error message if any attendee references a contact that does
    not exist, is deleted, belongs to another account, or has no primary
    number; None when everything is fine. Free-text attendees (no
    contact_id) are still accepted for backward compatibility."""
    for a in attendees or []:
        cid = a.get("contact_id") if isinstance(a, dict) else None
        if not cid:
            continue
        try:
            uid = uuid.UUID(str(cid))
        except ValueError:
            return f"Attendee '{a.get('name')}' has an invalid contact reference"
        c = (await db.execute(select(Contact).where(Contact.id == uid))).scalar_one_or_none()
        if not c or c.deleted_at is not None:
            return f"Contact for '{a.get('name')}' no longer exists"
        if account_id is not None and c.account_id != account_id:
            return f"Contact '{a.get('name')}' belongs to a different account than this meeting"
        if not can_complete_contact(c):
            return f"Add a primary phone number for '{full_name(c.first_name, c.last_name)}' before adding them to a MOM"
    return None


def expiry_from(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + timedelta(days=DELETE_REQUEST_TTL_DAYS)
