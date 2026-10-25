"""Canonical Leads SPANCO stage ladder — single source of truth for backend
and frontend alike.

This fixes, for Leads, the exact class of bug Pipeline.tsx's own code
comment already flags for pipeline deals: a frontend-hardcoded stage list
silently drifting out of sync with what the backend can actually set.
Nothing outside this module should hardcode a stage key or label — the
frontend fetches GET /leads/stages instead.

Provenance: sourced directly from WEP Solutions' own live Kylas CRM
configuration (Amit, 2026-10-24, via five screenshots of
app.kylas.io/sales/leads/list), handed over as "the right SPANCO" —
explicitly superseding nothing silently. A *different* 6-letter
S-P-A-N-C-O draft already exists in
fluidgo-mom-action-governance-design.md §11, scoped to PipelineDeal /
Opportunity rather than Lead, dated 2026-10-13, itself still "awaiting
confirmation." Both are real proposals; which one is "the" SPANCO is an
open decision for Amit, tracked in claude/README.md Open Items — do not
treat either as settled by code existing for it.

Two of Kylas's seven stage labels were truncated in the screenshots
("Scope Finalization/P..." and "Techno-Commercial ...") — SP5 and SP6 below
are a best-effort reconstruction, not a transcription. Confirm exact
wording against the live Kylas instance before treating these two as final.

Config-driven, not hardcoded: callers go through get_lead_stages(), which
checks the `feature_flags` row for key="leads_spanco_stages" first and only
falls back to DEFAULT_LEAD_STAGES if no row exists, the row is disabled, or
its config has no usable stage list. This is the concrete answer to Amit's
2026-10-24 instruction — "ensure the product scalability and a MSP where
standard features can be offered and wepsol customized can be
disabled/enabled as per customer requirement" — applied at the smallest
safe scope: a different customer's stage ladder becomes a feature_flags
config edit, not a code change or a redeploy. This is deliberately NOT
multi-tenancy: there is still no org/account/tenant entity and no tenant
isolation anywhere in the schema (fluidgo-roadmap-v2.md decision gate #1,
left for Amit). feature_flags.org_scope exists so that bigger decision, if
and when made, doesn't require reshaping this table.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureFlag

LEADS_STAGES_FLAG_KEY = "leads_spanco_stages"
LEADS_KANBAN_FLAG_KEY = "leads_kanban_view"

# key, label, sort_order (left-to-right column order, matches Kylas exactly),
# is_terminal, outcome (won|lost|None), color (board dot / accent).
DEFAULT_LEAD_STAGES: list[dict] = [
    {"key": "sp1_identifying",        "label": "SP1 · Identifying Opportunities",    "sort_order": 1,  "is_terminal": False, "outcome": None,   "color": "#94A3B8"},
    {"key": "sp2_profiling_bant",     "label": "SP2 · Profiling (BANT)",              "sort_order": 2,  "is_terminal": False, "outcome": None,   "color": "#60A5FA"},
    {"key": "sp3_understanding",      "label": "SP3 · Understanding the Opportunity", "sort_order": 3,  "is_terminal": False, "outcome": None,   "color": "#38BDF8"},
    {"key": "sp4_qualification_bant", "label": "SP4 · Qualification (BANT)",          "sort_order": 4,  "is_terminal": False, "outcome": None,   "color": "#34D399"},
    {"key": "sp5_scope_proposal",     "label": "SP5 · Scope Finalization / Proposal", "sort_order": 5,  "is_terminal": False, "outcome": None,   "color": "#A78BFA"},
    {"key": "sp6_techno_commercial",  "label": "SP6 · Techno-Commercial Discussion",  "sort_order": 6,  "is_terminal": False, "outcome": None,   "color": "#F472B6"},
    {"key": "sp7_negotiation",        "label": "SP7 · Negotiation",                   "sort_order": 7,  "is_terminal": False, "outcome": None,   "color": "#FB923C"},
    {"key": "hold",                   "label": "Hold",                                     "sort_order": 8,  "is_terminal": False, "outcome": None,   "color": "#CBD5E1"},
    {"key": "won",                    "label": "Won",                                      "sort_order": 9,  "is_terminal": True,  "outcome": "won",  "color": "#22C55E"},
    {"key": "closed_unqualified",     "label": "Closed · Unqualified",                "sort_order": 10, "is_terminal": True,  "outcome": "lost", "color": "#9CA3AF"},
    {"key": "closed_lost",            "label": "Closed · Lost",                       "sort_order": 11, "is_terminal": True,  "outcome": "lost", "color": "#EF4444"},
]


async def get_feature_flag(db: AsyncSession, key: str) -> Optional[FeatureFlag]:
    """Global lookup only (org_scope IS NULL) — fluidGo has no tenant concept
    yet; see module docstring. Preferring an org-scoped row over the global
    one, once an org concept exists, is a future additive change here."""
    result = await db.execute(
        select(FeatureFlag).where(FeatureFlag.key == key, FeatureFlag.org_scope.is_(None))
    )
    return result.scalar_one_or_none()


async def get_lead_stages(db: AsyncSession) -> list[dict]:
    """The active stage ladder: the feature_flags config override if one is
    enabled and has a non-empty stage list, else DEFAULT_LEAD_STAGES. Never
    returns an empty list — a misconfigured override (enabled but no usable
    config) still falls back, so the Kanban board can never end up with zero
    columns because of a bad flag edit."""
    flag = await get_feature_flag(db, LEADS_STAGES_FLAG_KEY)
    if flag and flag.enabled and flag.config and flag.config.get("stages"):
        return flag.config["stages"]
    return DEFAULT_LEAD_STAGES


async def is_kanban_enabled(db: AsyncSession) -> bool:
    """Absence of a row means "ship enabled by default", not "disabled" —
    only an explicit enabled=false row turns the board off."""
    flag = await get_feature_flag(db, LEADS_KANBAN_FLAG_KEY)
    if flag is None:
        return True
    return flag.enabled


def is_valid_stage_key(key: str, stages: list[dict]) -> bool:
    return any(s["key"] == key for s in stages)


def default_stage_for_status(status: str) -> str:
    """Backfill / fallback heuristic only (Rambo Commander, 2026-10-24) — maps
    the coarse Lead.status lifecycle onto a starting SPANCO stage when no
    stage has been explicitly set yet. A judgment call, not a Kylas fact:
    reviewable and overridable per-lead at any time via PATCH
    /leads/{id}/stage. See migration 0038's backfill and claude/README.md
    Open Items.

    'converted' -> 'won' deserves a word: a converted lead has already been
    promoted to a pipeline deal, i.e. it did its job as a lead. Kylas's own
    model treats a lead reaching its terminal success state as "Won" on the
    Leads board even though the deal itself then lives on a separate
    Opportunity pipeline — this mirrors that, rather than leaving converted
    leads stranded mid-ladder.
    """
    return {
        "new": "sp1_identifying",
        "qualified": "sp3_understanding",
        "proposal": "sp5_scope_proposal",
        "closed_won": "won",
        "closed_lost": "closed_lost",
        "converted": "won",
    }.get(status, "sp1_identifying")
