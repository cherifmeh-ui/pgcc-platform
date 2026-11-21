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
        r'require_permission\\(\\s*["\\']([^"\\']+)["\\']'
        r'(?:\\s*,\\s*["\\']([^"\\']+)["\\'])?\\s*\\)'
    )
    undeclared = []
    for endpoint_file in endpoints_dir.glob("*.py"):
        source = endpoint_file.read_text(encoding="utf-8")
        for match in declaration_pattern.finditer(source):
            module, action = match.group(1), match.group(2) or "read"
            if module not in PERMISSIONS or action not in PERMISSIONS.get(module, {}):
                undeclared.append(f"{endpoint_file.name}: {module}:{action}")
    assert undeclared == [], f"Endpoint permissions missing from RBAC matrix: {undeclared}"
