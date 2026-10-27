import asyncio
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException

from app.services.export_guard import can_export, export_guard
from app.routers.accounts import can_see_account, can_set_region, account_scope_filter


def U(role, region="India - West", business="fluidpro", id_="u1"):
    return NS(id=id_, role=role, region=region, business=business)


def A(region="India - West", business="fluidpro", created_by="x", owner=None):
    return NS(region=region, business=business, created_by=created_by, primary_owner_id=owner)


@pytest.mark.parametrize("role", ["rep", "inside_sales", "pre_sales"])
def test_sales_roles_cannot_export(role):
    assert not can_export(U(role))


@pytest.mark.parametrize("role", ["manager", "regional_manager", "crm_admin", "business_head", "coo", "ceo", "super_admin", "finance", "hr"])
def test_leaders_and_admins_can_export(role):
    assert can_export(U(role))


def test_guard_blocks_rep_and_governance_but_not_when_unrestricted():
    req = NS(query_params={}, client=None, headers={})
    with pytest.raises(HTTPException) as e:
        asyncio.run(export_guard("X")(req, None, U("rep")))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        asyncio.run(export_guard("X")(req, None, U("governance")))


def test_region_visibility():
    rep = U("rep")
    assert can_see_account(A("India - West"), rep)
    assert not can_see_account(A("India - North"), rep)
    assert can_see_account(A(None), rep)                      # legacy, unassigned
    assert can_see_account(A("India - North", created_by="u1"), rep)
    assert can_see_account(A("India - North"), U("ceo"))
    assert can_see_account(A("India - North"), U("crm_admin"))
    assert can_see_account(A("India - North"), U("business_head"))
    assert not can_see_account(A("India - North", business="floxtax"), U("business_head"))
    assert account_scope_filter(U("ceo")) is None


def test_only_business_wide_roles_set_region():
    for r in ("business_head", "coo", "ceo", "super_admin", "crm_admin"):
        assert can_set_region(U(r)), r
    for r in ("rep", "manager", "regional_manager", "inside_sales"):
        assert not can_set_region(U(r)), r


def test_region_list_chooser_matches_set_region():
    assert can_set_region(U("business_head")) and not can_set_region(U("rep"))
