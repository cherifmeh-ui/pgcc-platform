"""Tests unitaires du contrat d'administration des comptes."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.admin_users import AdminUserResponse, AdminUserUpdate
from app.utils.rbac import PERMISSIONS, role_has_permission


def test_user_management_permission_is_admin_only():
    assert role_has_permission("admin", "users", "manage")
    assert not role_has_permission("executive", "users", "manage")
    assert not role_has_permission("auditor", "users", "manage")
    assert not role_has_permission("viewer", "users", "manage")
    assert not role_has_permission("admin", "users", "delete")


def test_admin_user_update_normalizes_role_and_text():
    payload = AdminUserUpdate(
        full_name="  Utilisateur PGCC  ",
        department="  Direction IT ",
        role="  AUDITOR ",
        is_active=False,
    )
    assert payload.full_name == "Utilisateur PGCC"
    assert payload.department == "Direction IT"
    assert payload.role == "auditor"
    assert payload.is_active is False


@pytest.mark.parametrize("role", ["root", "superuser", "", "admin;drop"])
def test_admin_user_update_rejects_unknown_roles(role):
    with pytest.raises(ValidationError):
        AdminUserUpdate(role=role)


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "email",
        "password_hash",
        "auth_version",
        "mfa_secret",
        "backup_codes_hashed",
        "mfa_enabled",
        "must_change_password",
    ],
)
def test_admin_user_update_rejects_unmanaged_or_sensitive_fields(forbidden_field):
    with pytest.raises(ValidationError):
        AdminUserUpdate.model_validate({forbidden_field: "attacker-controlled"})


def test_admin_user_response_never_exposes_credentials_or_mfa_secrets():
    fields = set(AdminUserResponse.model_fields)
    assert not fields.intersection(
        {
            "password_hash",
            "mfa_secret",
            "backup_codes_hashed",
            "failed_login_attempts",
        }
    )
    user = AdminUserResponse(
        id=uuid4(),
        email="user@example.test",
        full_name="PGCC Test",
        department=None,
        role="viewer",
        is_active=True,
        mfa_enabled=False,
        must_change_password=False,
        auth_version=0,
        failed_login_attempts=0,
        locked_until=None,
        last_login_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payload = user.model_dump()
    assert "password_hash" not in payload
    assert "mfa_secret" not in payload
    assert "backup_codes_hashed" not in payload


def test_admin_user_routes_are_registered_and_protected_by_users_manage():
    root = Path(__file__).parents[1] / "app" / "api" / "v1"
    router_source = (root / "router.py").read_text(encoding="utf-8")
    endpoint_source = (
        root / "endpoints" / "admin_users.py"
    ).read_text(encoding="utf-8")
    assert "admin_users_router" in router_source
    assert 'prefix="/admin/users"' in endpoint_source
    assert endpoint_source.count('require_permission("users", "manage")') == 5
    assert '"users"' in PERMISSIONS


def test_mutating_admin_routes_revalidate_actor_under_row_locks():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "admin_users.py"
    ).read_text(encoding="utf-8")
    assert source.count("_lock_authorized_admin(") == 4  # helper + 3 mutations
    assert source.count("expected_auth_version = int(current_user.auth_version or 0)") == 3
    assert ".execution_options(populate_existing=True)" in source
