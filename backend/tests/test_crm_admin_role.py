"""CRM Admin role — added 2026-10-22 for Inside Sales/Marketing Ops (per Amit:
"a role for inside sales and marketing who handle CRM like giving access,
onboarding, offboarding, see the leads of all people, see opportunities,
closures etc.").

Design (see app/models/__init__.py's "crm_admin" entry and
can_provision_any_role() for the full rationale): scope="all" gives it
org-wide read + reassign reach for free via resolve_visible_user_ids
(covered by test_permission_service.py's test_all_scope_roles_see_everyone).
Its user-provisioning authority is a DECOUPLED capability flag
(can_provision_any_role), not a high numeric level — level stays 30, same
tier as regional_manager — specifically so it never inherits level-gated
authority elsewhere (FGA approval, DSR approval chains, financial
dashboards) that nobody asked it to have. These tests lock in the two
halves of that design: the flag itself, and every users.py call site that
must honor it (especially the one hard rule that survives every bypass —
nobody provisions a super_admin through this role).
"""
import pytest

from app.models import ROLE_HIERARCHY, can_provision_any_role, role_level
from app.routers.users import _can_create_role


def test_crm_admin_is_scope_all_with_provisioning_flag():
    entry = ROLE_HIERARCHY["crm_admin"]
    assert entry["scope"] == "all"
    assert entry["level"] == 30  # descriptive seniority only — not an authority lever
    assert entry.get("can_provision_any_role") is True


def test_crm_admin_keeps_default_financial_visibility():
    """Unlike governance, Amit explicitly scoped this role to include
    financial visibility (closures/opportunity value) — so, unlike
    governance's can_see_financials: False, crm_admin must NOT set it."""
    assert "can_see_financials" not in ROLE_HIERARCHY["crm_admin"]


@pytest.mark.parametrize("role", [
    "rep", "inside_sales", "pre_sales", "manager", "service_delivery_manager",
    "hr", "finance", "regional_manager", "bu_head", "governance",
    "business_head", "practice_head", "coo", "ceo", "super_admin",
])
def test_can_provision_any_role_defaults_false_for_every_other_role(role):
    assert can_provision_any_role(role) is False


def test_can_provision_any_role_true_only_for_crm_admin():
    assert can_provision_any_role("crm_admin") is True


def test_can_provision_any_role_unknown_role_defaults_false():
    assert can_provision_any_role("not_a_real_role") is False


# ── _can_create_role (users.py) ───────────────────────────────────────────
@pytest.mark.parametrize("target", [
    "rep", "manager", "regional_manager", "business_head", "coo", "ceo", "governance",
])
def test_crm_admin_can_create_any_role_except_super_admin(target):
    assert _can_create_role("crm_admin", target) is True


def test_crm_admin_cannot_create_super_admin():
    assert _can_create_role("crm_admin", "super_admin") is False


def test_super_admin_still_cannot_create_super_admin():
    """Regression guard: nobody creates a super_admin via this endpoint —
    this predates crm_admin and must not have been loosened by it."""
    assert _can_create_role("super_admin", "super_admin") is False


def test_crm_admin_itself_follows_normal_level_rule_when_targeted():
    """crm_admin is level 30 — a regional_manager (also level 30) still
    cannot create a crm_admin, same as any other equal-level role. The
    capability flag only grants EXTRA authority to act, it doesn't change
    what level crm_admin itself sits at for everyone else's comparisons."""
    assert _can_create_role("regional_manager", "crm_admin") is False
    assert _can_create_role("business_head", "crm_admin") is True


@pytest.mark.parametrize(("actor", "target", "expected"), [
    ("business_head", "manager", True),        # unaffected regression case
    ("manager", "business_head", False),       # unaffected regression case
    ("manager", "manager", False),             # equal level still blocked
    ("regional_manager", "manager", True),
])
def test_can_create_role_unaffected_for_non_provisioning_roles(actor, target, expected):
    assert _can_create_role(actor, target) is expected
