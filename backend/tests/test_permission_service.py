"""Data-scope isolation is the highest-risk area per the v2 risk register (a bug here
leaks cross-manager or, once Variable Pay ships, compensation data). These tests mock
the repository layer so scope-resolution logic is verified without a real DB — the
repos themselves are thin pass-throughs already exercised via manual E2E testing."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from app.services.permission_service import resolve_visible_user_ids


def _user(id_="u1", org_role_key=None, bu="West"):
    return SimpleNamespace(id=id_, org_role_key=org_role_key, bu=bu)


@pytest.mark.asyncio
async def test_no_org_role_defaults_to_own_data_only():
    user = _user(org_role_key=None)
    result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert result == [user.id]


@pytest.mark.asyncio
async def test_unknown_role_key_defaults_to_own_data_only():
    user = _user(org_role_key="sales")
    with patch("app.services.permission_service.role_repo.get_role", new=AsyncMock(return_value=None)):
        result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert result == [user.id]


@pytest.mark.asyncio
async def test_own_scope_sees_only_self():
    user = _user(org_role_key="sales")
    role = SimpleNamespace(data_scope="own")
    with patch("app.services.permission_service.role_repo.get_role", new=AsyncMock(return_value=role)):
        result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert result == [user.id]


@pytest.mark.asyncio
async def test_practice_head_sees_everything():
    user = _user(org_role_key="practice_head")
    role = SimpleNamespace(data_scope="practice")
    with patch("app.services.permission_service.role_repo.get_role", new=AsyncMock(return_value=role)):
        result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert result is None  # None == no restriction == sees everyone


@pytest.mark.asyncio
async def test_admin_all_scope_sees_everything():
    user = _user(org_role_key="admin")
    role = SimpleNamespace(data_scope="all")
    with patch("app.services.permission_service.role_repo.get_role", new=AsyncMock(return_value=role)):
        result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert result is None


@pytest.mark.asyncio
async def test_bu_scope_restricted_to_same_bu_users():
    user = _user(org_role_key="bu_head", bu="West")
    role = SimpleNamespace(data_scope="bu")
    same_bu_users = [SimpleNamespace(id="a"), SimpleNamespace(id="b")]
    with patch("app.services.permission_service.role_repo.get_role", new=AsyncMock(return_value=role)), \
         patch("app.services.permission_service.role_repo.list_users_in_bu", new=AsyncMock(return_value=same_bu_users)) as list_bu:
        result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert list_bu.call_args[0][1] == "West"
    assert result == ["a", "b"]


@pytest.mark.asyncio
async def test_team_scope_falls_back_to_bu_until_reporting_line_exists():
    """Documented Phase 1 limitation: no manager_id FK on users yet, so 'team' scope
    is intentionally the same as 'bu' scope for now (see permission_service.py)."""
    user = _user(org_role_key="manager", bu="West")
    role = SimpleNamespace(data_scope="team")
    same_bu_users = [SimpleNamespace(id="a")]
    with patch("app.services.permission_service.role_repo.get_role", new=AsyncMock(return_value=role)), \
         patch("app.services.permission_service.role_repo.list_users_in_bu", new=AsyncMock(return_value=same_bu_users)):
        result = await resolve_visible_user_ids(db=AsyncMock(), current_user=user)
    assert result == ["a"]
