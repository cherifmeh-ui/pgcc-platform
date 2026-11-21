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
