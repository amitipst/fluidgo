#!/usr/bin/env python3
"""Populate the Contacts master from old free-text leads/deals and link them (v1.5.0).

Dry-run by default; nothing is written without --apply.

  Default            link only: a name matching exactly one existing Company
                     (case/punctuation/"Pvt Ltd" insensitive) is linked.
  --create           ALSO create the Companies (and Contacts) that do not exist
                     yet, from the company / contact names already typed on
                     leads and deals, then link everything. Created Contacts
                     have no phone yet and are flagged incomplete, so people
                     can edit and complete them in Contacts.

Never auto-merged: "Sunpack Group" / "Sunpack Systems" become separate companies
and are printed under POSSIBLE DUPLICATES for a person to rename/merge.

    cd backend && python ../scripts/backfill_company_links.py --create           # report
    cd backend && python ../scripts/backfill_company_links.py --create --apply   # write
"""
import argparse
import asyncio
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Account, Contact, Lead, PipelineDeal, User  # noqa: E402
from app.services import company_backfill_service as bf  # noqa: E402
from app.services.contact_service import full_name  # noqa: E402


async def main(apply: bool, create: bool) -> None:
    async with AsyncSessionLocal() as db:
        biz = {u.id: (u.business or "fluidpro") for u in (await db.execute(select(User))).scalars().all()}
        accounts = (await db.execute(select(Account))).scalars().all()
        by_key: dict[tuple, Account] = {(bf.norm_company(a.name), a.business): a for a in accounts}
        contacts = (await db.execute(select(Contact).where(Contact.deleted_at.is_(None), Contact.status == "active"))).scalars().all()
        people: dict = defaultdict(dict)
        for c in contacts:
            people[c.account_id][bf.norm_person(full_name(c.first_name, c.last_name))] = c

        rows = []
        for model, label, attr in ((Lead, "lead", "contact_name"), (PipelineDeal, "deal", "primary_contact")):
            for r in (await db.execute(select(model).where(model.account_id.is_(None), model.is_seed == False))).scalars().all():  # noqa: E712
                rows.append((label, r, attr))

        # 1) companies that need creating, one per (normalised name, business)
        spellings: dict[tuple, list] = defaultdict(list)
        owners: dict[tuple, Counter] = defaultdict(Counter)
        for _, r, _ in rows:
            if not bf.is_usable_company(r.company):
                continue
            key = (bf.norm_company(r.company), biz.get(r.user_id, "fluidpro"))
            spellings[key].append(r.company)
            owners[key][r.user_id] += 1
        new_accounts: list[Account] = []
        if create:
            for key, names in sorted(spellings.items()):
                if key in by_key:
                    continue
                acc = Account(name=bf.display_name(names), business=key[1],
                              primary_owner_id=owners[key].most_common(1)[0][0])
                new_accounts.append(acc)
                by_key[key] = acc
                print(f"CREATE company '{acc.name}' ({key[1]}) from {len(names)} record(s)")
            if apply:
                db.add_all(new_accounts)
                await db.flush()

        # 2) link rows; create contacts where a person name is present
        linked = review = made_contacts = 0
        for label, r, attr in rows:
            key = (bf.norm_company(r.company), biz.get(r.user_id, "fluidpro"))
            acc = by_key.get(key)
            if acc is None:
                print(f"REVIEW {label} {r.id} '{r.company}' — {'no usable company name' if not bf.is_usable_company(r.company) else 'no company yet (run with --create)'}")
                review += 1
                continue
            person = getattr(r, attr) or ""
            contact = None
            acc_id = getattr(acc, "id", None)
            if bf.is_usable_person(person):
                pk = bf.norm_person(person)
                contact = people[acc_id].get(pk) if acc_id else None
                if contact is None and create:
                    first, last = bf.split_person(person)
                    contact = Contact(account_id=acc_id, first_name=first, last_name=last, incomplete=True,
                                      owner_user_id=r.user_id, created_by=None)
                    if apply:
                        db.add(contact)
                        await db.flush()
                        people[acc_id][pk] = contact
                    made_contacts += 1
                    print(f"CREATE contact '{person}' at '{acc.name}' (incomplete: add phone in Contacts)")
            print(f"LINK   {label} {r.id} '{r.company}' -> '{acc.name}'" + (f" / {person}" if contact else ""))
            if apply:
                r.account_id = acc_id
                if contact is not None:
                    r.contact_id = contact.id
            linked += 1

        names = [a.name for a in new_accounts] or [a.name for a in by_key.values()]
        pairs = bf.similar_pairs(sorted(set(names)))
        if pairs:
            print("\nPOSSIBLE DUPLICATES — review in Contacts (rename/merge by hand, nothing was merged):")
            for a, b in pairs:
                print(f"  '{a}'  ~  '{b}'")
        if apply:
            await db.commit()
        print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {len(new_accounts)} companies and {made_contacts} contacts "
              f"{'created' if apply else 'would be created'}; {linked} records linked, {review} need a person's decision.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--create", action="store_true", help="create missing companies/contacts from existing records")
    a = ap.parse_args()
    asyncio.run(main(a.apply, a.create))
