"""Companies (accounts) API — /api/accounts. Company-first Contacts (v1.4.0).

Reuses the existing Account table and get_or_create_account(); this router adds
the explicit create/list/detail the UI needs so a company is created first and
contacts are added under it. Companies are a shared team asset (so the team can
work opportunities together); contacts inside stay subject to contact rules."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Account, Contact, User, ROLE_HIERARCHY
from app.services.deps import get_current_user, deny_governance
from app.services.permission_service import resolve_visible_user_ids
from app.services.audit_service import audit
from app.services import contact_service as cs
from app.services import geo_service, website_service

router = APIRouter()


class AccountIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=2)
    postal_code: Optional[str] = Field(None, max_length=20)
    allow_duplicate_reason: Optional[str] = None
    region: Optional[str] = Field(None, max_length=100)   # honoured only for business-wide roles


class AccountPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=2)
    postal_code: Optional[str] = Field(None, max_length=20)
    region: Optional[str] = Field(None, max_length=100)   # business-wide roles only; audited


def _guard(user: User, write: bool):
    if user.role in cs.NO_CONTACT_ACCESS_ROLES:
        raise HTTPException(403, "Your role has no access to companies")
    if write:
        deny_governance(user)


# ── Region ownership (v1.6.3) ────────────────────────────────────────────────
# A company belongs to the region of the people who created it. Roles whose scope is all / hr /
# finance see every company; a business head sees their business; everyone else sees their own
# region plus companies not yet assigned a region (legacy records, so nothing disappears).
# Only business-wide roles may create in, or move a company to, another region.
_GLOBAL_SCOPES = {"all", "hr", "finance"}


def _scope_of(user) -> str:
    return ROLE_HIERARCHY.get(user.role, {}).get("scope", "own")


def can_set_region(user) -> bool:
    return _scope_of(user) in ("all", "business")


def account_scope_filter(user):
    """SQL condition limiting companies to the caller's scope, or None for no limit."""
    sc = _scope_of(user)
    if sc in _GLOBAL_SCOPES:
        return None
    if sc == "business":
        return Account.business == (user.business or "fluidpro")
    return or_(Account.region == user.region, Account.region.is_(None),
               Account.created_by == user.id, Account.primary_owner_id == user.id)


def can_see_account(a, user) -> bool:
    sc = _scope_of(user)
    if sc in _GLOBAL_SCOPES:
        return True
    if sc == "business":
        return a.business == (user.business or "fluidpro")
    return a.region is None or a.region == user.region or user.id in (a.created_by, a.primary_owner_id)


def _clean_name(n: str) -> str:
    n = " ".join((n or "").split())
    if len(n) < 2 or not any(ch.isalnum() for ch in n):
        raise HTTPException(422, "Enter a valid company name")
    return n


def _address(data: dict) -> dict:
    keys = ("address_line1", "address_line2", "city", "state", "country", "postal_code")
    try:
        return geo_service.validate_address({k: data[k] for k in keys if k in data})
    except ValueError as e:
        raise HTTPException(422, str(e))


def _clean_website(w: Optional[str]) -> Optional[str]:
    """Optional. Stored in canonical form (https://…); a site being unreachable
    never blocks saving — only a malformed address does."""
    if not w or not w.strip():
        return None
    try:
        return website_service.normalize_url(w)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _ser(a: Account, contact_count: int = 0) -> dict:
    return {"id": str(a.id), "name": a.name, "business": a.business, "region": a.region,
            "industry": a.industry, "website": a.website, "city": a.city,
            "address_line1": a.address_line1, "address_line2": a.address_line2, "state": a.state,
            "country": a.country, "postal_code": a.postal_code,
            "primary_owner_id": str(a.primary_owner_id) if a.primary_owner_id else None,
            "created_by": str(a.created_by) if a.created_by else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "contact_count": contact_count}


async def _similar(db: AsyncSession, name: str, business: str, exclude_id=None) -> list[Account]:
    key = cs.company_key(name)
    rows = (await db.execute(select(Account).where(Account.business == business))).scalars().all()
    return [a for a in rows if a.id != exclude_id and key and cs.company_key(a.name) == key]


class WebsiteCheckIn(BaseModel):
    url: str = Field(max_length=300)


@router.post("/check-website")
async def check_website(body: WebsiteCheckIn, user: User = Depends(get_current_user)):
    """Is this company website live? Advisory only — the UI warns but never blocks."""
    _guard(user, write=False)
    if website_service.rate_limited(str(user.id)):
        raise HTTPException(429, "Too many website checks — wait a minute and try again")
    return await website_service.check_website(body.url)


@router.get("/geo")
async def geo_lists(user: User = Depends(get_current_user)):
    """Country / state pick-lists + postal hints (static reference data)."""
    return geo_service.geo_payload()


@router.get("")
async def list_accounts(q: Optional[str] = None, limit: int = Query(300, le=1000), offset: int = 0,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=False)
    counts = (select(Contact.account_id, func.count(Contact.id).label("n"))
              .where(Contact.deleted_at.is_(None), Contact.status == "active")
              .group_by(Contact.account_id).subquery())
    stmt = select(Account, func.coalesce(counts.c.n, 0)).outerjoin(counts, counts.c.account_id == Account.id)
    if q and q.strip():
        stmt = stmt.where(func.lower(Account.name).like(f"%{q.strip().lower()}%"))
    scope_cond = account_scope_filter(user)
    if scope_cond is not None:
        stmt = stmt.where(scope_cond)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await db.execute(stmt.order_by(func.lower(Account.name)).limit(limit).offset(offset))).all()
    return {"total": total, "items": [_ser(a, int(n)) for a, n in rows]}


@router.post("", status_code=201)
async def create_account(body: AccountIn, bg: BackgroundTasks, request: Request,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=True)
    name = _clean_name(body.name)
    business = user.business or "fluidpro"
    region = (body.region or "").strip() or None if can_set_region(user) else None
    if region is None:
        region = user.region
    if region is None and not can_set_region(user):
        raise HTTPException(422, "Your profile has no region, so a company cannot be created. Ask an admin to set your region.")
    all_dups = await _similar(db, name, business)
    dups = [d for d in all_dups if can_see_account(d, user)]
    if len(all_dups) > len(dups):
        # exists in a region this user cannot see: do not reveal it, do not allow a parallel copy
        raise HTTPException(409, {"message": "This company already exists in another region. Ask that region's manager or a CRM admin.",
                                  "duplicates": []})
    if dups and len((body.allow_duplicate_reason or "").strip()) < 5:
        raise HTTPException(409, {"message": "This company already exists",
                                  "duplicates": [_ser(a) for a in dups]})
    addr = _address(body.model_dump(exclude_unset=True))
    a = Account(name=name, business=business, region=region, industry=(body.industry or "").strip() or None,
                website=_clean_website(body.website), created_by=user.id, **addr)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    bg.add_task(audit, db, user, "account.create", "account", str(a.id),
                f"Created company {a.name} in region {region}" + (f" (duplicate override: {body.allow_duplicate_reason})" if dups else ""),
                None, request)
    return _ser(a)


@router.get("/{account_id}")
async def get_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    _guard(user, write=False)
    a = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not a or not can_see_account(a, user):
        raise HTTPException(404, "Company not found")
    stmt = select(Contact).where(Contact.account_id == a.id, Contact.deleted_at.is_(None))
    vf = cs.visibility_filter(await resolve_visible_user_ids(db, user), user.id)
    if vf is not None:
        stmt = stmt.join(Account, Account.id == Contact.account_id).where(vf)
    contacts = (await db.execute(stmt.order_by(Contact.status, Contact.first_name))).scalars().all()
    out = _ser(a, sum(1 for c in contacts if c.status == "active"))
    # job-change links: where did people who left go, and who came from elsewhere
    ids = [c.id for c in contacts]
    moved_to: dict = {}
    if ids:
        rows = (await db.execute(select(Contact, Account).join(Account, Account.id == Contact.account_id)
                .where(Contact.previous_contact_id.in_(ids), Contact.deleted_at.is_(None)))).all()
        for m, acc in rows:
            moved_to.setdefault(m.previous_contact_id, []).append({"id": str(m.id), "account_id": str(acc.id), "account_name": acc.name})
    prev_ids = [c.previous_contact_id for c in contacts if c.previous_contact_id]
    from_names: dict = {}
    if prev_ids:
        rows = (await db.execute(select(Contact.id, Account.name).join(Account, Account.id == Contact.account_id)
                .where(Contact.id.in_(prev_ids)))).all()
        from_names = {cid: n for cid, n in rows}
    out["contacts"] = [{**cs.serialize(c, a.name), "moved_to": moved_to.get(c.id, []),
                        "moved_from_account": from_names.get(c.previous_contact_id)} for c in contacts]
    out["can_edit"] = user.role != "governance"
    return out


@router.patch("/{account_id}")
async def patch_account(account_id: uuid.UUID, body: AccountPatch, bg: BackgroundTasks, request: Request,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _guard(user, write=True)
    a = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not a or not can_see_account(a, user):
        raise HTTPException(404, "Company not found")
    data = body.model_dump(exclude_unset=True)
    if "region" in data:
        if not can_set_region(user):
            raise HTTPException(403, "Only a business head, CRM admin or admin can change a company's region")
        data["region"] = (data["region"] or "").strip() or None
    if "name" in data:
        data["name"] = _clean_name(data["name"])
        if await _similar(db, data["name"], a.business, exclude_id=a.id):
            raise HTTPException(409, "Another company with this name already exists")
    if "website" in data:
        data["website"] = _clean_website(data["website"])
    if any(k in data for k in ("address_line1", "address_line2", "city", "state", "country", "postal_code")):
        # validate against the company's existing country when the edit doesn't change it
        probe = {"country": a.country, **data}
        cleaned = _address(probe)
        data.update({k: v for k, v in cleaned.items() if k in data or k == "country"})
    old_region = a.region
    changed = [k for k, v in data.items() if getattr(a, k) != v]
    for k in changed:
        setattr(a, k, data[k])
    await db.commit()
    if changed:
        bg.add_task(audit, db, user, "account.update", "account", str(a.id),
                    "Updated company: " + ", ".join(sorted(changed)), {"fields": sorted(changed), **({"region": {"from": old_region, "to": a.region}} if "region" in changed else {})}, request)
    return _ser(a)
