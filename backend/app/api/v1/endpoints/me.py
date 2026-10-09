# backend/app/api/v1/endpoints/me.py
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.utils.rbac import get_effective_permissions

router = APIRouter(prefix="/me", tags=["Profil & Permissions"])


@router.get("/profile")
async def my_profile(current_user: User = Depends(get_current_user)):
    """Retourne le profil de l'utilisateur connecté."""
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "department": current_user.department,
        "role": current_user.role,
        "mfa_enabled": current_user.mfa_enabled,
        "must_change_password": current_user.must_change_password,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
    }


@router.get("/permissions")
async def my_permissions(current_user: User = Depends(get_current_user)):
    """
    Retourne la matrice complète des permissions effectives du rôle.
    Le frontend utilise cette réponse pour afficher/masquer les menus et boutons.
    MAIS le backend reste seul juge lors de chaque appel d'API métier.
    """
    perms = get_effective_permissions(current_user.role)
    return {
        "role": current_user.role,
        "permissions": perms,
    }