"""Deal rules — one place that decides what a valid pipeline deal looks like.

Added in v1.5.0 (2026-10-26) after Amit's review of the live screens:

  * "ARR and One-time should be mandatory for any deal value"
  * "win probability ... as per SP1, SP2, SP3, SP4 etc stages automatically"
  * "any deal which is in negotiation stage should be minimum 70% win probability"
  * "any new lead, deal should start with contact creation if not already present"

Why a service and not code inside the router: the same rules must hold on
every write path (create, edit, lead -> deal conversion, the forecast sheet's
inline win-% edit) and must be unit-testable without a database. The router
asks this module; it never re-implements a rule.

Config, not code (per rambo-constitution and Amit's 2026-10-24 MSP ask): the
per-stage default and floor live in DEFAULT_STAGE_RULES below and can be
overridden by a `feature_flags` row with key "deal_rules" — no redeploy to
change a number. A missing row means "use the shipped defaults".

Stage defaults (5/10/20/30/45/60/75, floor 70 at SP7, Won 100) were set on
2026-10-26 by Amit: "consider yourself a BU head with better prediction" for
the numbers, SP1..SP7 through Won as the ladder, and 70% as the negotiation
floor. They only ever *pre-fill* a value the rep can raise; they never block,
except the floor. Tunable in feature_flags 'deal_rules' without a deploy.

WON means the customer's email / LOI / PO / agreement was received (won_basis,
won_at). REVENUE is recognised when the tax invoice is raised (invoiced_at).

Stage keys come from lead_stage_service's Kylas-sourced ladder. Whether that
ladder or the 6-stage SPANCO draft in fluidgo-mom-action-governance-design.md
section 11 is "the" SPANCO is still Amit's open decision (README Open Item 8);
keeping the numbers in config means that decision does not force a code change.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lead_stage_service import get_feature_flag

DEAL_RULES_FLAG_KEY = "deal_rules"

# key -> default win % pre-filled when a deal enters the stage, and the floor
# (a rep may go higher, never lower). Only sp7's floor of 70 is Amit's number.
DEFAULT_STAGE_RULES: dict[str, dict] = {
    "sp1_identifying":        {"default": 5,  "floor": 0, "category": "pipeline"},
    "sp2_profiling_bant":     {"default": 10, "floor": 0, "category": "pipeline"},
    "sp3_understanding":      {"default": 20, "floor": 0, "category": "pipeline"},
    "sp4_qualification_bant": {"default": 30, "floor": 0, "category": "pipeline"},
    "sp5_scope_proposal":     {"default": 45, "floor": 0, "category": "pipeline"},
    "sp6_techno_commercial":  {"default": 60, "floor": 0, "category": "best_case"},
    "sp7_negotiation":        {"default": 75, "floor": 70, "category": "commit"},
    "won":                    {"default": 100, "floor": 100, "category": "closed"},
}

# v1.6.0 — where a lead becomes a deal (Amit, 2026-10-26: "SP5 to SP7 to Won").
# Salesforce-style: the rule is configuration (a validation rule), not code.
#   convert_min_stage   a lead may be converted once it has reached this stage
#   deal_start_stage    a converted / newly created deal starts here at the earliest
#   new_deal_min_stage  a NEW deal cannot be created below this stage (earlier
#                       stages are worked as a Lead); existing deals are untouched
# Set convert_min_stage to sp5 in feature_flags 'deal_rules' for a stricter gate.
STAGE_ORDER = ["sp1_identifying", "sp2_profiling_bant", "sp3_understanding", "sp4_qualification_bant",
               "sp5_scope_proposal", "sp6_techno_commercial", "sp7_negotiation", "won"]
LEAD_EXIT_STAGES = {"hold", "closed_unqualified", "closed_lost"}
FORECAST_CATEGORY_LABELS = {"pipeline": "Pipeline", "best_case": "Best case",
                            "commit": "Commit", "closed": "Closed"}

# What counts as the customer's commitment (Amit, 2026-10-26).
WON_BASES = ("email", "loi", "po", "agreement")
WON_BASIS_LABELS = {"email": "Customer email", "loi": "LOI", "po": "Purchase order", "agreement": "Agreement"}

# Stages (legacy `PipelineDeal.stage` values) where revenue split / link rules
# do not apply: closing a deal as lost or dropping it must never be blocked by
# missing paperwork on an old row.
EXEMPT_FROM_REVENUE_RULE = {"closed_lost", "dropped", "on_hold"}
WON, LOST = "closed_won", ("closed_lost", "dropped")


class RuleViolation(ValueError):
    """A business-rule failure with a message safe to show a sales rep."""


async def get_rules(db: AsyncSession) -> dict:
    """Shipped defaults, overlaid with the optional feature_flags override."""
    rules = {
        "stages": {k: dict(v) for k, v in DEFAULT_STAGE_RULES.items()},
        "require_company_contact": True,
        "require_revenue_split": True,
        "convert_min_stage": "sp4_qualification_bant",
        "deal_start_stage": "sp5_scope_proposal",
        "new_deal_min_stage": "sp5_scope_proposal",
        "notify_finance_on_won": True,
    }
    flag = await get_feature_flag(db, DEAL_RULES_FLAG_KEY)
    if flag and flag.enabled and flag.config:
        cfg = flag.config
        for key, vals in (cfg.get("stages") or {}).items():
            if isinstance(vals, dict):
                rules["stages"].setdefault(key, {"default": 0, "floor": 0}).update(
                    {k: int(v) for k, v in vals.items() if k in ("default", "floor")})
                if vals.get("category") in FORECAST_CATEGORY_LABELS:
                    rules["stages"][key]["category"] = vals["category"]
        for k in ("require_company_contact", "require_revenue_split", "notify_finance_on_won"):
            if k in cfg:
                rules[k] = bool(cfg[k])
        for k in ("convert_min_stage", "deal_start_stage", "new_deal_min_stage"):
            if cfg.get(k) in STAGE_ORDER:
                rules[k] = cfg[k]
    return rules


def stage_rule(sp_stage: Optional[str], rules: dict) -> Optional[dict]:
    return rules["stages"].get(sp_stage) if sp_stage else None


def validate_revenue_split(recurring, one_time, stage: Optional[str], rules: dict) -> None:
    """ARR and One-time are both required (zero is a valid answer — a pure
    licence sale has ARR 0) and the deal must be worth something. Skipped for
    lost/dropped/on-hold so an old incomplete row can still be closed."""
    if not rules.get("require_revenue_split", True) or stage in EXEMPT_FROM_REVENUE_RULE:
        return
    if recurring is None or one_time is None:
        raise RuleViolation("Enter both ARR and One-time revenue (use 0 if there is none).")
    if recurring < 0 or one_time < 0:
        raise RuleViolation("ARR and One-time revenue cannot be negative.")
    if recurring + one_time <= 0:
        raise RuleViolation("ARR and One-time cannot both be 0 — enter the deal's value.")


def validate_won(basis: Optional[str], won_at) -> None:
    """A deal can only be marked won with evidence of the customer's commitment."""
    if basis not in WON_BASES:
        raise RuleViolation("To mark a deal Won, record the customer's commitment: "
                            "email, LOI, purchase order or agreement.")
    if won_at is None:
        raise RuleViolation("Enter the date the customer's commitment was received.")


def derive_deal_value(recurring, one_time) -> Optional[float]:
    """Legacy `deal_value` is kept in sync as ARR + One-time so every older
    screen and export that still reads it shows the same total."""
    if recurring is None and one_time is None:
        return None
    return round(float(recurring or 0) + float(one_time or 0), 2)


def resolve_win_probability(stage: Optional[str], sp_stage: Optional[str],
                            requested: Optional[int], rules: dict) -> Optional[int]:
    """The win % to store.

    * won = 100, lost/dropped = 0 regardless of what was sent;
    * with an SP stage: nothing sent -> the stage default; sent below the
      stage floor -> RuleViolation (SP7 Negotiation can never be under 70);
    * without an SP stage (legacy deals): the rep's number untouched, or None.
    """
    if stage == WON:
        return 100
    if stage in LOST:
        return 0
    rule = stage_rule(sp_stage, rules)
    if rule is None:
        return requested
    if requested is None:
        return max(rule["default"], rule["floor"])
    if requested < rule["floor"]:
        raise RuleViolation(
            f"A deal in {sp_stage_label(sp_stage)} must have at least {rule['floor']}% win probability.")
    return requested


def sp_stage_label(sp_stage: Optional[str]) -> str:
    return {
        "sp1_identifying": "SP1 Identifying", "sp2_profiling_bant": "SP2 Profiling",
        "sp3_understanding": "SP3 Understanding", "sp4_qualification_bant": "SP4 Qualification",
        "sp5_scope_proposal": "SP5 Scope / Proposal", "sp6_techno_commercial": "SP6 Techno-Commercial",
        "sp7_negotiation": "SP7 Negotiation", "won": "Won",
    }.get(sp_stage or "", sp_stage or "this stage")


def forecast_probability(deal, rules: Optional[dict] = None) -> Optional[int]:
    """The ONE definition of a deal's win % for weighted forecasts.

    Before v1.5.0 three screens used three formulas (Opportunities: value x
    ai_closure_pct = 1.29Cr; Pipeline sheet: win_probability = 1.64Cr;
    Executive Digest: ai_closure_pct only = 2.5L), so the same pipeline showed
    three different 'weighted' numbers. Order: closed states, then the rep's
    own win %, then the SP-stage default, then the AI estimate. None = unknown.
    """
    rules = rules or {"stages": DEFAULT_STAGE_RULES}
    if deal.stage == WON:
        return 100
    if deal.stage in LOST:
        return 0
    if getattr(deal, "win_probability", None) is not None:
        return int(deal.win_probability)
    rule = stage_rule(getattr(deal, "sp_stage", None), rules)
    if rule:
        return max(rule["default"], rule["floor"])
    ai = getattr(deal, "ai_closure_pct", None)
    return int(ai) if ai is not None else None


def needs_revenue_split(deal) -> bool:
    """True for a live deal still missing ARR or One-time (legacy rows)."""
    if deal.stage in EXEMPT_FROM_REVENUE_RULE or deal.stage in LOST:
        return False
    return deal.recurring_revenue is None or deal.one_time_revenue is None


def _idx(stage: Optional[str]) -> int:
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1


def validate_convert(lead_stage: Optional[str], rules: dict) -> None:
    """A lead may only become a deal once qualified (default: SP4 reached).
    Hold / closed leads cannot be converted — reopen them first."""
    need = rules.get("convert_min_stage", "sp4_qualification_bant")
    if lead_stage in LEAD_EXIT_STAGES:
        raise RuleViolation("This lead is on hold or closed. Reopen it before converting it to a deal.")
    if _idx(lead_stage) < _idx(need):
        raise RuleViolation(
            f"Qualify the lead first: it can become a deal once it reaches {sp_stage_label(need)} "
            f"(it is at {sp_stage_label(lead_stage) if lead_stage else 'no stage'}).")


def deal_start_stage(lead_stage: Optional[str], rules: dict) -> str:
    """Stage a converted deal opens at: the later of the configured start stage
    and the lead's own progress; a lead already Won opens at Negotiation."""
    start = rules.get("deal_start_stage", "sp5_scope_proposal")
    if lead_stage == "won":
        lead_stage = "sp7_negotiation"
    return lead_stage if _idx(lead_stage) > _idx(start) else start


def validate_new_deal_stage(sp_stage: Optional[str], rules: dict) -> None:
    """New deals begin at SP5+ — earlier stages are worked as a Lead. Closed-won
    entries and legacy edits are not affected (this runs on create only)."""
    need = rules.get("new_deal_min_stage", "sp5_scope_proposal")
    if _idx(sp_stage) < _idx(need):
        raise RuleViolation(
            f"New deals start at {sp_label_short(need)} or later. Work earlier stages as a Lead "
            f"and convert it once qualified.")


def sp_label_short(stage: str) -> str:
    return sp_stage_label(stage).split(" ")[0]


def forecast_category(deal, rules: Optional[dict] = None) -> Optional[str]:
    """Salesforce-style forecast category derived from the deal's stage:
    pipeline / best_case / commit / closed. Lost deals have none."""
    rules = rules or {"stages": DEFAULT_STAGE_RULES}
    if deal.stage == WON:
        return "closed"
    if deal.stage in LOST or deal.stage == "on_hold":
        return None
    rule = stage_rule(getattr(deal, "sp_stage", None), rules)
    return rule.get("category") if rule else None
