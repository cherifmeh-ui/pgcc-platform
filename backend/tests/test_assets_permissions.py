from app.utils.rbac import role_has_permission


def test_asset_inventory_permissions_are_restricted_to_authorized_roles():
    assert role_has_permission("admin", "assets", "read")
    assert role_has_permission("auditor", "assets", "read")
    assert role_has_permission("executive", "assets", "read")
    assert not role_has_permission("viewer", "assets", "read")
    assert not role_has_permission("auditor", "assets", "create")
    assert role_has_permission("admin", "assets", "create")


def test_asset_risk_link_listing_requires_risk_read():
    assert role_has_permission("admin", "risks", "read")
    assert not role_has_permission("viewer", "assets", "read")
    assert role_has_permission("viewer", "risks", "read")
    assert not role_has_permission("limited", "risks", "read")
    assert not role_has_permission("limited", "assets", "read")


def test_asset_export_is_restricted_to_admin_and_auditor():
    assert role_has_permission("admin", "assets", "export")
    assert role_has_permission("auditor", "assets", "export")
    assert not role_has_permission("executive", "assets", "export")
    assert not role_has_permission("viewer", "assets", "export")

import re
from pathlib import Path

from app.utils.rbac import PERMISSIONS


def test_endpoint_permissions_are_declared_in_rbac_matrix():
    endpoints_dir = Path(__file__).parents[1] / "app" / "api" / "v1" / "endpoints"
    declaration_pattern = re.compile(
        r"""require_permission\(\s*['"]([^'"]+)['"]"""
        r"""(?:\s*,\s*['"]([^'"]+)['"])?\s*\)"""
    )
    undeclared = []
    discovered = set()
    for endpoint_file in endpoints_dir.glob("*.py"):
        source = endpoint_file.read_text(encoding="utf-8")
        for match in declaration_pattern.finditer(source):
            module, action = match.group(1), match.group(2) or "read"
            discovered.add((module, action))
            if module not in PERMISSIONS or action not in PERMISSIONS.get(module, {}):
                undeclared.append(f"{endpoint_file.name}: {module}:{action}")
    assert discovered, "No require_permission declarations were discovered; permission audit must not pass vacuously"
    assert undeclared == [], f"Endpoint permissions missing from RBAC matrix: {undeclared}"


import pytest
from fastapi import HTTPException

from app.api.deps import require_permission


@pytest.mark.parametrize(
    ("role", "action", "allowed"),
    [
        ("admin", "read", True),
        ("admin", "create", True),
        ("admin", "update", True),
        ("admin", "delete", True),
        ("admin", "export", True),
        ("executive", "read", True),
        ("executive", "create", False),
        ("executive", "update", False),
        ("executive", "delete", False),
        ("executive", "export", False),
        ("auditor", "read", True),
        ("auditor", "create", False),
        ("auditor", "update", False),
        ("auditor", "delete", False),
        ("auditor", "export", True),
        ("viewer", "read", False),
        ("viewer", "create", False),
        ("viewer", "update", False),
        ("viewer", "delete", False),
        ("viewer", "export", False),
        ("unknown", "read", False),
        ("", "read", False),
    ],
)
@pytest.mark.asyncio
async def test_asset_permission_dependency_enforces_full_role_action_matrix(
    role: str, action: str, allowed: bool
):
    dependency = require_permission("assets", action).dependency
    user = type("UserStub", (), {"role": role})()

    if allowed:
        assert await dependency(current_user=user) is user
    else:
        with pytest.raises(HTTPException) as exc:
            await dependency(current_user=user)
        assert exc.value.status_code == 403


@pytest.mark.parametrize(
    ("role", "asset_read", "risk_read", "supplier_asset_read", "asset_update", "risk_update", "supplier_manage_assets"),
    [
        ("admin", True, True, True, True, True, True),
        ("executive", True, True, False, False, False, False),
        ("auditor", True, True, True, False, False, False),
        ("viewer", False, True, False, False, False, False),
        ("unknown", False, False, False, False, False, False),
    ],
)
def test_cross_module_asset_risk_supplier_permissions_are_consistent(
    role,
    asset_read,
    risk_read,
    supplier_asset_read,
    asset_update,
    risk_update,
    supplier_manage_assets,
):
    """Lock down cross-module authorization intersections used by Cartography."""
    assert role_has_permission(role, "assets", "read") is asset_read
    assert role_has_permission(role, "risks", "read") is risk_read
    assert role_has_permission(role, "suppliers", "read_assets") is supplier_asset_read
    assert role_has_permission(role, "assets", "update") is asset_update
    assert role_has_permission(role, "risks", "update") is risk_update
    assert role_has_permission(role, "suppliers", "manage_assets") is supplier_manage_assets

    # Mutating cross-module links must never be available unless both sides
    # of the relationship can be updated by the same principal.
    if role_has_permission(role, "assets", "update") and role_has_permission(
        role, "risks", "update"
    ):
        assert role == "admin"
    if role_has_permission(role, "assets", "update") and role_has_permission(
        role, "suppliers", "manage_assets"
    ):
        assert role == "admin"
