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
