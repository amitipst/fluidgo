"""Contacts master API (v1.4.0-A) — /api/contacts. Rules live in
services/contact_service.py; this file is HTTP + persistence only."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Contact, ContactDeleteRequest, ContactDeleteApproval, Account, User
from app.services.deps import get_current_user, deny_governance
from app.services.permission_service import resolve_visible_user_ids
from app.services.audit_service import audit
from app.services.account_service import get_or_create_account
from app.services import contact_service as cs

router = APIRouter()


Salutation = Literal["Mr.", "Ms.", "Mrs.", "Mx.", "Dr.", "Prof.", "CA", "CS", "Er."]


def _name_v(v, required=True):
    try:
        return cs.valid_person_name(v, required=required)
    except ValueError as e:
        raise ValueError(str(e))


class ContactIn(BaseModel):
    account_id: Optional[uuid.UUID] = None
    account_name: Optional[str] = None          # alternative to account_id (get-or-create)
    salutation: Optional[Salutation] = None
    first_name: str = Field(min_length=1, max_length=100)
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_primary: str
    phone_secondary: Optional[str] = None
    linkedin_url: Optional[str] = None
    reports_to_contact_id: Optional[uuid.UUID] = None
    is_primary_contact: bool = False
    allow_duplicate_reason: Optional[str] = None
    previous_contact_id: Optional[uuid.UUID] = None   # set when this person moved here from another company

    @field_validator("first_name")
    @classmethod
    def _fn(cls, v): return _name_v(v)

    @field_validator("last_name")
    @classmethod
    def _ln(cls, v): return _name_v(v, required=False)

    @field_validator("linkedin_url")
    @classmethod
    def _li(cls, v):
        try: return cs.valid_linkedin(v)
        except ValueError as e: raise ValueError(str(e))


class ContactPatch(BaseModel):
    salutation: Optional[Salutation] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_primary: Optional[str] = None
    phone_secondary: Optional[str] = None
    linkedin_url: Optional[str] = None
    reports_to_contact_id: Optional[uuid.UUID] = None
    is_primary_contact: Optional[bool] = None
    status: Optional[str] = None                # active | left
    do_not_contact: Optional[bool] = None

    @field_validator("first_name")
    @classmethod
    def _fn(cls, v): return _name_v(v) if v is not None else v

    @field_validator("last_name")
    @classmethod
    def _ln(cls, v): return _name_v(v, required=False)

    @field_validator("linkedin_url")
    @classmethod
    def _li(cls, v):
        try: return cs.valid_linkedin(v)
        except ValueError as e: raise ValueError(str(e))


class DeleteRequestIn(BaseModel):
    reason: str = Field(min_length=5)


class DecisionIn(BaseModel):
    decision: str                                # approve | reject
    comment: Optional[str] = None


def _guard(user: User, write: bool):
    if user.role in cs.NO_CONTACT_ACCESS_ROLES:
        raise HTTPException(403, "Your role has no access to contacts")
    if write:
        deny_governance(user)


async def _load(db, cid, include_deleted=False) -> Contact:
    c = (await db.execute(select(Contact).where(Contact.id == cid))).scalar_one_or_none()
    if not c or (c.deleted_at is not None and not include_deleted):
        raise HTTPException(404, "Contact not found")
    return c


async def _can_edit(db, user: User, c: Contact) -> bool:
    if user.role == "super_admin" or c.created_by == user.id or c.owner_user_id == user.id:
        return True
    acct = (await db.execute(select(Account).where(Account.id == c.account_id))).scalar_one_or_none()
    if acct and acct.primary_owner_id == user.id:
        return True
    vis = await resolve_visible_user_ids(db, user)
    if vis is None:
        return True
    s = set(vis)
    return bool({c.created_by, c.owner_user_id, acct.primary_owner_id if acct else None} & s - {None})


@router.get("")
async def list_contacts(q: Optional[str] = None, account_id: Optional[uuid.UUID] = None,
                        incomplete: bool = False, include_left: bool = True,
                        limit: int = Query(200, le=500), offset: int = 0,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=False)
    stmt = (select(Contact, Account.name).join(Account, Account.id == Contact.account_id)
            .where(Contact.deleted_at.is_(None)))
    vf = cs.visibility_filter(await resolve_visible_user_ids(db, user), user.id)
    if vf is not None:
        stmt = stmt.where(vf)
    if account_id:
        stmt = stmt.where(Contact.account_id == account_id)
    if incomplete:
        stmt = stmt.where(or_(Contact.incomplete.is_(True), Contact.phone_primary.is_(None)))
    if not include_left:
        stmt = stmt.where(Contact.status == "active")
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Contact.first_name).like(like), func.lower(Contact.last_name).like(like),
                              func.lower(Contact.email).like(like), Contact.phone_primary.like(f"%{q.strip()}%"),
                              func.lower(Account.name).like(like)))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await db.execute(stmt.order_by(Account.name, Contact.first_name).limit(limit).offset(offset))).all()
    return {"total": total, "items": [cs.serialize(c, n) for c, n in rows]}


@router.post("", status_code=201)
async def create_contact(body: ContactIn, bg: BackgroundTasks, request: Request,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=True)
    phone = cs.normalize_phone(body.phone_primary)
    if not phone:
        raise HTTPException(422, "A valid primary phone number is required")
    phone2 = None
    if body.phone_secondary:
        phone2 = cs.normalize_phone(body.phone_secondary)
        if not phone2:
            raise HTTPException(422, "Secondary phone number is not valid")
    if body.account_id:
        acct = (await db.execute(select(Account).where(Account.id == body.account_id))).scalar_one_or_none()
        if not acct:
            raise HTTPException(404, "Account not found")
    elif body.account_name and body.account_name.strip():
        acct = await get_or_create_account(db, body.account_name, business=user.business or "fluidpro")
    else:
        raise HTTPException(422, "account_id or account_name is required")

    cand = {"first_name": body.first_name.strip(), "last_name": (body.last_name or "").strip() or None,
            "email": body.email, "phone_primary": phone}
    dups = await cs.find_duplicates(db, acct.id, cand)
    if dups:
        reason = (body.allow_duplicate_reason or "").strip()
        if len(reason) < 5:
            raise HTTPException(409, {"message": "Possible duplicate contact on this account",
                                      "duplicates": dups})
    prev = None
    if body.previous_contact_id:
        prev = await _load(db, body.previous_contact_id)
        if prev.account_id == acct.id:
            raise HTTPException(422, "A person who moved must be added to a different company")
    c = Contact(account_id=acct.id, salutation=body.salutation, previous_contact_id=prev.id if prev else None, first_name=cand["first_name"],
                last_name=cand["last_name"], designation=body.designation, department=body.department,
                email=str(body.email).lower() if body.email else None, phone_primary=phone,
                phone_secondary=phone2, linkedin_url=body.linkedin_url,
                reports_to_contact_id=body.reports_to_contact_id, is_primary_contact=body.is_primary_contact,
                status="active", incomplete=False, owner_user_id=user.id, created_by=user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    bg.add_task(audit, db, user, "contact.create", "contact", str(c.id),
                f"Created contact {cs.full_name(c.first_name, c.last_name)} on {acct.name}"
                + (f" (duplicate override: {body.allow_duplicate_reason})" if dups else ""), None, request)
    return cs.serialize(c, acct.name)


# NOTE: static paths must be declared before "/{contact_id}".
@router.get("/recycle-bin")
async def recycle_bin(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in cs.RESTORE_ROLES:
        raise HTTPException(403, "Only governance, management heads or super admin can view the recycle bin")
    rows = (await db.execute(select(Contact, Account.name).join(Account, Account.id == Contact.account_id)
            .where(Contact.deleted_at.is_not(None)).order_by(Contact.deleted_at.desc()))).all()
    return {"items": [cs.serialize(c, n) for c, n in rows]}


async def _expire(db: AsyncSession):
    now = datetime.now(timezone.utc)
    stale = (await db.execute(select(ContactDeleteRequest).where(
        ContactDeleteRequest.status == "pending", ContactDeleteRequest.expires_at < now))).scalars().all()
    for r in stale:
        r.status, r.decided_at = "expired", now
    if stale:
        await db.commit()


async def _request_view(db, r: ContactDeleteRequest, user: User) -> dict:
    c = (await db.execute(select(Contact).where(Contact.id == r.contact_id))).scalar_one_or_none()
    requester = (await db.execute(select(User).where(User.id == r.requested_by))).scalar_one_or_none()
    apps = (await db.execute(select(ContactDeleteApproval).where(
        ContactDeleteApproval.request_id == r.id))).scalars().all()
    slots = {a.approver_slot for a in apps}
    slot = cs.approver_slot(user, requester, slots) if requester and r.status == "pending" else None
    already = any(a.approver_user_id == user.id for a in apps)
    return {"id": str(r.id), "contact_id": str(r.contact_id),
            "contact_name": cs.full_name(c.first_name, c.last_name) if c else None,
            "requested_by": str(r.requested_by), "requested_by_name": requester.name if requester else None,
            "reason": r.reason, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "approvals": [{"slot": a.approver_slot, "decision": a.decision, "comment": a.comment,
                           "approver_user_id": str(a.approver_user_id)} for a in apps],
            "can_decide": bool(slot) and not already and user.role != "hr", "my_slot": slot}


@router.get("/delete-requests")
async def list_delete_requests(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=False)
    await _expire(db)
    stmt = select(ContactDeleteRequest).order_by(ContactDeleteRequest.created_at.desc()).limit(200)
    vis = await resolve_visible_user_ids(db, user)
    org_wide_approver = user.role in ("governance", "inside_sales", "super_admin")
    if vis is not None and not org_wide_approver:
        stmt = stmt.where(ContactDeleteRequest.requested_by.in_(list(vis) + [user.id]))
    rows = (await db.execute(stmt)).scalars().all()
    return {"items": [await _request_view(db, r, user) for r in rows]}


@router.get("/{contact_id}")
async def get_contact(contact_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    _guard(user, write=False)
    c = await _load(db, contact_id)
    acct = (await db.execute(select(Account).where(Account.id == c.account_id))).scalar_one_or_none()
    out = cs.serialize(c, acct.name if acct else None)
    out["can_edit"] = user.role != "governance" and await _can_edit(db, user, c)
    # job-change history: where this person went / where they came from
    moved_to = (await db.execute(select(Contact, Account.name).join(Account, Account.id == Contact.account_id)
                .where(Contact.previous_contact_id == c.id, Contact.deleted_at.is_(None)))).all()
    out["moved_to"] = [{"id": str(m.id), "account_id": str(m.account_id), "account_name": n} for m, n in moved_to]
    if c.previous_contact_id:
        pc = (await db.execute(select(Contact, Account.name).join(Account, Account.id == Contact.account_id)
              .where(Contact.id == c.previous_contact_id))).first()
        out["moved_from"] = {"id": str(pc[0].id), "account_name": pc[1]} if pc else None
    return out


@router.patch("/{contact_id}")
async def patch_contact(contact_id: uuid.UUID, body: ContactPatch, bg: BackgroundTasks, request: Request,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=True)
    c = await _load(db, contact_id)
    if not await _can_edit(db, user, c):
        raise HTTPException(403, "You can't edit this contact")
    data = body.model_dump(exclude_unset=True)
    if "phone_primary" in data:
        p = cs.normalize_phone(data["phone_primary"])
        if not p:
            raise HTTPException(422, "A valid primary phone number is required (it can't be blanked)")
        data["phone_primary"] = p
    if data.get("phone_secondary"):
        p2 = cs.normalize_phone(data["phone_secondary"])
        if not p2:
            raise HTTPException(422, "Secondary phone number is not valid")
        data["phone_secondary"] = p2
    if "first_name" in data and not (data["first_name"] or "").strip():
        raise HTTPException(422, "First name can't be blank")
    if data.get("status") not in (None, "active", "left"):
        raise HTTPException(422, "status must be 'active' or 'left'")
    if data.get("email"):
        data["email"] = str(data["email"]).lower()
    changed = {}
    for k, v in data.items():
        if getattr(c, k) != v:
            changed[k] = v
            setattr(c, k, v)
    if "status" in changed:
        c.left_at = datetime.now(timezone.utc) if c.status == "left" else None
    if c.phone_primary:
        c.incomplete = False
    c.updated_at = datetime.now(timezone.utc)
    await db.commit()
    if changed:
        bg.add_task(audit, db, user, "contact.update", "contact", str(c.id),
                    "Updated contact: " + ", ".join(sorted(changed)), {"fields": sorted(changed)}, request)
    return cs.serialize(c)


@router.post("/{contact_id}/delete-request", status_code=201)
async def request_delete(contact_id: uuid.UUID, body: DeleteRequestIn, bg: BackgroundTasks, request: Request,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=True)
    c = await _load(db, contact_id)
    if not await _can_edit(db, user, c):
        raise HTTPException(403, "You can't request deletion of this contact")
    await _expire(db)
    open_req = (await db.execute(select(ContactDeleteRequest).where(
        ContactDeleteRequest.contact_id == c.id, ContactDeleteRequest.status == "pending"))).scalar_one_or_none()
    if open_req:
        raise HTTPException(409, "A deletion request for this contact is already pending")
    r = ContactDeleteRequest(contact_id=c.id, requested_by=user.id, reason=body.reason.strip(),
                             status="pending", expires_at=cs.expiry_from())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    bg.add_task(audit, db, user, "contact.delete_request", "contact", str(c.id),
                f"Requested deletion: {body.reason.strip()}", None, request)
    return await _request_view(db, r, user)


@router.post("/delete-requests/{request_id}/decision")
async def decide_delete(request_id: uuid.UUID, body: DecisionIn, bg: BackgroundTasks, request: Request,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=False)
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be 'approve' or 'reject'")
    await _expire(db)
    r = (await db.execute(select(ContactDeleteRequest).where(ContactDeleteRequest.id == request_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Request not found")
    if r.status != "pending":
        raise HTTPException(409, f"Request is already {r.status}")
    requester = (await db.execute(select(User).where(User.id == r.requested_by))).scalar_one()
    apps = (await db.execute(select(ContactDeleteApproval).where(
        ContactDeleteApproval.request_id == r.id))).scalars().all()
    if any(a.approver_user_id == user.id for a in apps):
        raise HTTPException(409, "You have already decided this request")
    slot = cs.approver_slot(user, requester, {a.approver_slot for a in apps})
    if not slot:
        raise HTTPException(403, "You are not an approver for this request")
    if any(a.approver_slot == slot and a.decision == "approve" for a in apps) and body.decision == "approve":
        raise HTTPException(409, f"The {slot} approval is already recorded")
    if body.decision == "reject" and not (body.comment or "").strip():
        raise HTTPException(422, "A comment is required when rejecting")
    db.add(ContactDeleteApproval(request_id=r.id, approver_user_id=user.id, approver_slot=slot,
                                 decision=body.decision, comment=body.comment))
    await db.flush()
    state = cs.decide_state([{"decision": a.decision, "approver_slot": a.approver_slot} for a in apps]
                            + [{"decision": body.decision, "approver_slot": slot}])
    now = datetime.now(timezone.utc)
    if state != "pending":
        r.status, r.decided_at = state, now
    if state == "approved":
        c = await _load(db, r.contact_id, include_deleted=True)
        c.deleted_at, c.deleted_by = now, r.requested_by
    await db.commit()
    bg.add_task(audit, db, user, f"contact.delete_{body.decision}", "contact", str(r.contact_id),
                f"{body.decision} deletion as {slot}; request now {state}", None, request)
    return await _request_view(db, r, user)


@router.post("/{contact_id}/restore")
async def restore_contact(contact_id: uuid.UUID, bg: BackgroundTasks, request: Request,
                          db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in cs.RESTORE_ROLES:
        raise HTTPException(403, "Only governance, management heads or super admin can restore contacts")
    c = await _load(db, contact_id, include_deleted=True)
    if c.deleted_at is None:
        raise HTTPException(409, "Contact is not deleted")
    c.deleted_at, c.deleted_by = None, None
    await db.commit()
    bg.add_task(audit, db, user, "contact.restore", "contact", str(c.id), "Restored contact", None, request)
    return cs.serialize(c)
