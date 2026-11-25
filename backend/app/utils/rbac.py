# backend/app/utils/rbac.py
from enum import Enum
from typing import Any


class Role(str, Enum):
    ADMIN = "admin"          # RSSI / Administrateur Système
    EXECUTIVE = "executive"  # PDG / Direction Générale
    AUDITOR = "auditor"      # Auditeur interne / externe / Conformité ANCS
    VIEWER = "viewer"        # Consultation simple (Employés, Managers non-tech)


# Matrice de permissions backend.
# C'est la SOURCE DE VÉRITÉ. Le frontend reçoit cette liste au login
# mais n'a AUCUN pouvoir décisionnel. Seul le backend autorise/refuse.
PERMISSIONS: dict[str, dict[str, list[str]]] = {
    # --- Dashboard & Vue Globale ---
    "dashboard": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
    },
    
    # --- Registre des Risques SI ---
    "risks": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
        "comment": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "accept": [Role.ADMIN.value, Role.EXECUTIVE.value],  # Acceptation du risque résiduel
    },
    
    # --- Plan d'Actions Correctives (PAC) ---
    "actions": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "close": [Role.ADMIN.value, Role.EXECUTIVE.value],
        "delete": [Role.ADMIN.value],
    },
    
    # --- Documents & Politiques Sécurité (Phase 11 - RAG) ---
    "documents": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],   # Upload PSSI/Procédures réservé Admin/RSSI
        "update": [Role.ADMIN.value],
        "approve": [Role.ADMIN.value, Role.EXECUTIVE.value],
        "delete": [Role.ADMIN.value],
    },
    
    # --- Normes ISO 27001/27002 ---
    "iso27002": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "update": [Role.ADMIN.value],   # Marquer un contrôle comme couvert manuellement
    },
    
    # --- Inventaire des Applications Critiques (Module Apps) ---
    # ⚠️ IMPORTANT : Le nom du module doit être EXACTEMENT "apps" 
    # pour matcher avec require_permission("apps", ...) dans apps.py et reports.py
    "apps": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
    },
    
    # --- Cartographie des actifs et dépendances ---
    "assets": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
        "export": [Role.ADMIN.value, Role.AUDITOR.value],
    },
    
    # --- Gestion des fournisseurs et tiers (TPRM) ---
    "suppliers": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "read_contacts": [Role.ADMIN.value, Role.AUDITOR.value],
        "read_contracts": [Role.ADMIN.value, Role.AUDITOR.value],
        "manage_contracts": [Role.ADMIN.value],
        "read_assessments": [Role.ADMIN.value, Role.AUDITOR.value],
        "read_assets": [Role.ADMIN.value, Role.AUDITOR.value],
        "read_access_requests": [Role.ADMIN.value, Role.AUDITOR.value],
        "request_access": [Role.ADMIN.value],
        "decide_access": [Role.ADMIN.value],
        "revoke_access": [Role.ADMIN.value],
        "expire_access": [Role.ADMIN.value],
        "review_access": [Role.ADMIN.value],
        "manage_assets": [Role.ADMIN.value],
        "manage_risks": [Role.ADMIN.value],
        "assess": [Role.ADMIN.value],
        "validate_assessment": [Role.ADMIN.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "archive": [Role.ADMIN.value],
        "manage_contacts": [Role.ADMIN.value],
        "export": [Role.ADMIN.value, Role.AUDITOR.value],
    },
    
    # --- Menaces & Vulnérabilités ---
    "threats": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "create": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
    },
    
    # --- Incidents & Notifications Réglementaires (ANCS) ---
    "incidents": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "create": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value, Role.VIEWER.value],
        "update": [Role.ADMIN.value],
        "notify_ancs": [Role.ADMIN.value],  # Notification ANCS réservée RSSI/Admin
    },
    
    # --- Privileged Access Management (PAM) ---
    "pam": {
        "read": [Role.ADMIN.value],           # PAM = sensible → admin uniquement
        "update": [Role.ADMIN.value],
        "delete": [Role.ADMIN.value],
    },
    
    # --- Configuration Système ---
    "settings": {
        "read": [Role.ADMIN.value],
        "update": [Role.ADMIN.value],
    },
    
    # --- Journal d'Audit Immuable ---
    "security_log": {
        "read": [Role.ADMIN.value, Role.AUDITOR.value],  # Consultable par Admin/Auditor seulement
    },
    
    # --- Assistant IA Souverain (Phi3/Llama3) ---
    # --- Administration du cycle de vie des comptes ---\n    "users": {\n        "manage": [Role.ADMIN.value],\n    },\n\n    "ai_assistant": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "use": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
    },
    
    # --- Rapports Stratégiques & Synthèse DG (Phase 8) ---
    "reports": {
        "read": [Role.ADMIN.value, Role.EXECUTIVE.value, Role.AUDITOR.value],
        "generate": [Role.ADMIN.value, Role.EXECUTIVE.value], # ← Permet la génération via bouton Dashboard
    },
}


def role_has_permission(role: str | None, module: str, action: str = "read") -> bool:
    """Vérifie si un rôle a une permission donnée."""
    if not role:
        return False

    clean_role = role.strip().lower()
    clean_module = module.strip().lower()
    clean_action = action.strip().lower()
    
    module_perms = PERMISSIONS.get(clean_module)
    if not module_perms:
        return False
    
    allowed_roles = module_perms.get(clean_action)
    if allowed_roles is None:
        return False
    
    return clean_role in allowed_roles


def get_effective_permissions(role: str | None) -> dict[str, Any]:
    """
    Retourne la liste des actions permises pour chaque module selon le rôle.
    Utilisé par l'endpoint /me/permissions pour alimenter le frontend.
    """
    if not role:
        return {}

    clean_role = role.strip().lower()
    result: dict[str, Any] = {}
    for module, actions in PERMISSIONS.items():
        allowed_actions = [
            action for action, roles in actions.items() if clean_role in roles
        ]
        if allowed_actions:
            result[module] = allowed_actions
    
    return result