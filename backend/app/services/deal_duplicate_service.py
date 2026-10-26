"""Duplicate alert for parallel deals (v1.6.0) — Salesforce "duplicate rule" in
Alert-and-allow mode.

Amit (2026-10-26): parallel deals on one company are fine ("2 or 3 deals can
run in a single customer") but must never be created silently. When a rep picks
a company/contact for a new lead or deal, the form asks this module what is
already open and shows it; the rep can open the existing record or carry on.
Nothing here blocks.

Visibility: the *existence* of an open deal (owner, stage) is shown to anyone
creating against the same company — that is the point of the alert — but the
money (ARR / One-time) is shown only for deals the user is allowed to see.
"""
from __future__ import annotations

from typing import Iterable, Optional

CLOSED_DEAL_STAGES = {"closed_won", "closed_lost", "dropped", "on_hold"}
CLOSED_LEAD_STATUSES = {"converted"}
CLOSED_LEAD_STAGES = {"hold", "won", "closed_unqualified", "closed_lost"}


def is_open_deal(deal) -> bool:
    return deal.stage not in CLOSED_DEAL_STAGES and not getattr(deal, "archived", False)


def is_open_lead(lead) -> bool:
    return (lead.status not in CLOSED_LEAD_STATUSES and (lead.stage or "") not in CLOSED_LEAD_STAGES
            and not getattr(lead, "converted_to_deal_id", None))


def summarise(deals: Iterable, leads: Iterable, visible_ids: Optional[set], contact_id=None,
              owner_names: Optional[dict] = None, stage_label=lambda s: s or "") -> dict:
    """Pure: shape open deals/leads into the alert payload.
    visible_ids None = user can see everything (scope 'all')."""
    owner_names = owner_names or {}

    def can_see(owner_id) -> bool:
        return visible_ids is None or owner_id in visible_ids

    out_deals = []
    for d in deals:
        if not is_open_deal(d):
            continue
        row = {
            "id": str(d.id), "title": d.title or d.company, "company": d.company,
            "stage_label": stage_label(d.sp_stage) if d.sp_stage else d.stage,
            "owner": owner_names.get(d.user_id, ""), "mine": None,
            "same_contact": bool(contact_id and d.contact_id == contact_id),
            "viewable": can_see(d.user_id),
        }
        if row["viewable"]:
            row["deal_value"] = float(d.deal_value) if d.deal_value is not None else None
        out_deals.append(row)
    out_leads = []
    for l in leads:
        if not is_open_lead(l):
            continue
        out_leads.append({
            "id": str(l.id), "company": l.company, "requirement": l.requirement,
            "stage": l.stage, "owner": owner_names.get(l.user_id, ""),
            "same_contact": bool(contact_id and l.contact_id == contact_id),
            "viewable": can_see(l.user_id),
        })
    out_deals.sort(key=lambda r: (not r["same_contact"], r["title"] or ""))
    return {"deals": out_deals, "leads": out_leads, "count": len(out_deals) + len(out_leads)}
