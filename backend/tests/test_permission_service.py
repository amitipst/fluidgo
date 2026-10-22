"""Data-scope isolation is the highest-risk area per the v2 risk register (a bug here
leaks cross-manager or, once Variable Pay ships, compensation data).

Rewritten 2026-10-14: the old tests mocked a `role_repo` / `org_role_key` model that
no longer exists, so 7 of them failed on every run and the CI gate could not be made
blocking. These tests target the real implementation: scope comes from
ROLE_HIERARCHY[user.role], and the database layer is replaced by a fake session so
the scope-resolution logic is verified without Postgres."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models import ROLE_HIERARCHY
from app.services import permission_service as ps
from app.services.permission_service import resolve_visible_user_ids


def _user(role, id_="u1", region="India - West", business="fluidpro"):
    return SimpleNamespace(id=id_, role=role, region=region, business=business)


def _db(*row_ids):
    """Fake AsyncSession: every execute() returns rows of 1-tuples."""
    result = SimpleNamespace(all=lambda: [(i,) for i in row_ids])
    return SimpleNamespace(execute=AsyncMock(return_value=result))


def _subtree(ids):
    return patch.object(ps, "resolve_subtree_user_ids", new=AsyncMock(return_value=ids))


@pytest.mark.asyncio
async def test_unknown_role_defaults_to_own_data_only():
    with _subtree([]):
        result = await resolve_visible_user_ids(_db(), _user("no_such_role"))
    assert result == ["u1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["rep", "inside_sales", "pre_sales"])
async def test_field_roles_see_only_themselves(role):
    with _subtree([]):
        result = await resolve_visible_user_ids(_db(), _user(role))
    assert result == ["u1"]


@pytest.mark.asyncio
async def test_field_role_with_personal_reports_sees_them_too():
    """Dual-role support: a rep who is also someone's manager_id sees that person."""
    with _subtree(["r1", "r2"]):
        result = await resolve_visible_user_ids(_db(), _user("rep"))
    assert sorted(result) == ["r1", "r2", "u1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["coo", "ceo", "super_admin", "governance", "crm_admin"])
async def test_all_scope_roles_see_everyone(role):
    result = await resolve_visible_user_ids(_db(), _user(role))
    assert result is None  # None == no restriction


@pytest.mark.asyncio
async def test_all_scope_with_region_filter_narrows_to_that_region():
    db = _db("a", "b")
    result = await resolve_visible_user_ids(db, _user("coo"), region_filter="India - North")
    assert result == ["a", "b"]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["hr", "finance"])
async def test_hr_and_finance_see_all_active_users(role):
    result = await resolve_visible_user_ids(_db("a", "b", "c"), _user(role))
    assert result == ["a", "b", "c"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["business_head", "practice_head"])
async def test_business_head_sees_their_business_plus_personal_reports(role):
    with _subtree(["extra"]):
        result = await resolve_visible_user_ids(_db("a", "b"), _user(role))
    assert sorted(result) == ["a", "b", "extra"]


@pytest.mark.asyncio
async def test_business_head_region_filter_skips_dual_role_union():
    """An explicit single-region drill-down must not leak an out-of-region report."""
    sub = AsyncMock(return_value=["extra"])
    with patch.object(ps, "resolve_subtree_user_ids", new=sub):
        result = await resolve_visible_user_ids(
            _db("a"), _user("business_head"), region_filter="India - West"
        )
    assert result == ["a"]
    sub.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["regional_manager", "bu_head"])
async def test_regional_manager_and_deprecated_bu_head_share_region_scope(role):
    with _subtree([]):
        result = await resolve_visible_user_ids(_db("a", "b"), _user(role))
    assert result == ["a", "b"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["manager", "service_delivery_manager"])
async def test_manager_sees_full_reporting_chain(role):
    db = _db("should-not-be-used")
    with _subtree(["r1", "r2", "r3"]):
        result = await resolve_visible_user_ids(db, _user(role))
    assert result == ["r1", "r2", "r3"]
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_manager_with_no_reports_falls_back_to_region_and_business():
    with _subtree([]):
        result = await resolve_visible_user_ids(_db("a", "b"), _user("manager"))
    assert result == ["a", "b"]


def test_governance_has_all_scope_but_cannot_see_financials():
    from app.models import can_see_financials
    assert ROLE_HIERARCHY["governance"]["scope"] == "all"
    assert can_see_financials("governance") is False
    assert can_see_financials("rep") is True


def test_every_role_has_a_scope_the_resolver_understands():
    known = {"own", "team", "hr", "finance", "region", "business", "all"}
    for name, cfg in ROLE_HIERARCHY.items():
        assert cfg["scope"] in known, f"{name} has unhandled scope {cfg['scope']!r}"
