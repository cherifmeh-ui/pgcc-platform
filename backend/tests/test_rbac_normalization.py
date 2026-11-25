import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.utils.rbac import get_effective_permissions, role_has_permission


def test_rbac_normalizes_role_module_and_action_inputs():
    assert role_has_permission(" ADMIN ", " ASSETS ", " READ ")
    assert role_has_permission("Auditor", "assets", "export")
    assert get_effective_permissions(" ADMIN ") == get_effective_permissions("admin")


def test_rbac_denies_unknown_roles_modules_and_actions():
    assert not role_has_permission(None, "assets", "read")
    assert not role_has_permission("unknown", "assets", "read")
    assert not role_has_permission("admin", "unknown", "read")
    assert not role_has_permission("admin", "assets", "unknown")


def test_rbac_permissions_are_explicit_and_role_specific():
    assert role_has_permission("admin", "suppliers", "manage_assets")
    assert not role_has_permission("auditor", "suppliers", "manage_assets")
    assert not role_has_permission("viewer", "security_log", "read")

@pytest.mark.asyncio
async def test_get_current_user_enforces_mfa_for_case_variant_privileged_role(monkeypatch):
    from app.api import deps

    user = MagicMock(
        email="admin@example.test", role=" ADMIN ", is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=0,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(
        deps, "decode_token",
        lambda token, expected_type: {"sub": user.email, "role": "admin", "auth_version": 0},
    )

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            db=db,
        )
    assert exc.value.status_code == 403
    assert "MFA" in exc.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("token_role", [None, "", "admin", 7])
async def test_get_current_user_rejects_missing_or_mismatched_role_claim(monkeypatch, token_role):
    from app.api import deps

    user = MagicMock(
        email="viewer@example.test", role="viewer", is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=0,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(
        deps, "decode_token",
        lambda token, expected_type: {"sub": user.email, "role": token_role, "auth_version": 0},
    )

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            db=db,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_accepts_normalized_matching_role(monkeypatch):
    from app.api import deps

    user = MagicMock(
        email="viewer@example.test", role=" VIEWER ", is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=0,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(
        deps, "decode_token",
        lambda token, expected_type: {"sub": user.email, "role": "viewer", "auth_version": 0},
    )

    current = await deps.get_current_user(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
        db=db,
    )
    assert current is user


@pytest.mark.asyncio
@pytest.mark.parametrize("token_version", [None, True, -1, 1, "0"])
async def test_get_current_user_rejects_stale_auth_version(monkeypatch, token_version):
    from app.api import deps

    user = MagicMock(
        email="viewer@example.test", role="viewer", is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=0,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(
        deps, "decode_token",
        lambda token, expected_type: {
            "sub": user.email, "role": "viewer", "auth_version": token_version,
        },
    )

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            db=db,
        )
    assert exc.value.status_code == 401
    assert "Session révoquée" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_user_accepts_matching_auth_version(monkeypatch):
    from app.api import deps

    user = MagicMock(
        email="viewer@example.test", role="viewer", is_active=True,
        must_change_password=False, mfa_enabled=False, auth_version=4,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(
        deps, "decode_token",
        lambda token, expected_type: {
            "sub": user.email, "role": "viewer", "auth_version": 4,
        },
    )

    current = await deps.get_current_user(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
        db=db,
    )
    assert current is user
