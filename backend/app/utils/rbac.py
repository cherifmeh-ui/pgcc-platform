# backend/app/utils/rbac.py
from enum import Enum
from typing import Any


class Role(str, Enum):
    ADMIN = "admin"          # RSSI
    EXECUTIVE = "executive"  # PDG / Direction Générale
    AUDITOR = "auditor"      # Auditeur interne / externe
    VIEWER = "viewer"        # Consultation simple


# Matrice de permissions backend.
# C'est la SOURCE DE VÉRITÉ. Le frontend reçoit cette liste au login
# mais n'a AUCUN pouvoir décisionnel. Seul le backend autorise/refuse.
PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "dashboard": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
    },
    "risks": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
        "comment": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "accept": [Role.ADMIN.value, Role.EXECUTIVE.value],  # Acceptation du risque résiduel
    },
    "actions": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "close": [Role.ADMIN.value, Role.EXECUTIVE.value],
        "delete": [Role.ADMIN.value],
    },
    "documents": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "approve": [Role.ADMIN.value, Role.EXECUTIVE.value],
        "delete": [Role.ADMIN.value],
    },
    "iso27002": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "update": [Role.ADMIN.value],
    },
    "audits": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value, Role.AUDITOR.value],
        "update": [Role.ADMIN.value, Role.AUDITOR.value],
        "delete": [Role.ADMIN.value],
    },
    "apps": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
    },
    "threats": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
    },
    "incidents": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "create": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "update": [Role.ADMIN.value],
        "notify_ancs": [Role.ADMIN.value],  # Notification ANCS réservée RSSI
    },
    "pam": {
        "read": [Role.ADMIN.value],           # PAM = sensible → admin uniquement
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
    },
    "settings": {
        "read": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
    },
    "security_log": {
        "read": [Role.ADMIN.value, Role.AUDITOR.value],  # Journal d'audit consultable par auditor
    },
    "ai_assistant": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "use": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
    },
    "reports": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "generate": [Role.ADMIN.value, Role.EXECUTIVE.value],
    },
}


def role_has_permission(role: str | None, module: str, action: str = "read") -> bool:
    """Vérifie si un rôle a une permission donnée."""
    if not role:
        return False
    module_perms = PERMISSIONS.get(module)
    if not module_perms:
        return False
    allowed_roles = module_perms.get(action)
    if allowed_roles is None:
        return False
    return role in allowed_roles


def get_effective_permissions(role: str | None) -> dict[str, Any]:
    """
    Retourne la liste des actions permises pour chaque module selon le rôle.
    Utilisé par l'endpoint /me/permissions pour alimenter le frontend.
    """
    if not role:
        return {}
    result: dict[str, Any] = {}
    for module, actions in PERMISSIONS.items():
        allowed_actions = [
            action for action, roles in actions.items() if role in roles
        ]
        if allowed_actions:
            result[module] = allowed_actions
    return result