# backend/app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.utils.rbac import role_has_permission

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Récupère l'utilisateur courant à partir du JWT access.
    Valide :
    - présence du token ;
    - signature et expiration ;
    - type 'access' ;
    - existence utilisateur ;
    - compte actif ;
    - mot de passe temporaire changé ;
    - MFA activé pour rôles sensibles (admin/executive) ;
    - cohérence rôle token vs rôle base.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_token(token, expected_type="access")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    token_role = payload.get("role")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide : identité manquante.",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé.",
        )

    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Changement de mot de passe obligatoire avant accès.",
        )

    # Normalize the persisted role exactly as the RBAC matrix does. This keeps
    # privileged-role MFA enforcement fail-closed even if legacy data has case
    # or whitespace inconsistencies.
    normalized_role = (user.role or "").strip().lower()
    if normalized_role in {"admin", "executive"} and not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA obligatoire pour ce rôle.",
        )

    # Access tokens issued by this application always carry a role claim.
    # Reject missing/malformed claims and force re-authentication after role changes.
    if (
        not isinstance(token_role, str)
        or not token_role.strip()
        or token_role.strip().lower() != normalized_role
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rôle modifié ou absent. Veuillez vous reconnecter.",
        )

    # auth_version is incremented whenever a security-sensitive account field
    # changes. Enforce it on every authenticated request so old access tokens
    # are invalidated immediately, not merely when their short TTL expires.
    token_auth_version = payload.get("auth_version")
    current_auth_version = int(user.auth_version or 0)
    if (
        isinstance(token_auth_version, bool)
        or not isinstance(token_auth_version, int)
        or token_auth_version != current_auth_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session révoquée ou état de sécurité modifié. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: str):
    """Dépendance simple basée sur le rôle."""
    allowed_values = {role.strip().lower() for role in allowed_roles if role and role.strip()}

    async def dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = (current_user.role or "").strip().lower()
        if user_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : rôle insuffisant.",
            )
        return current_user

    return Depends(dependency)


def require_permission(module: str, action: str = "read"):
    """
    Dépendance FastAPI pour protéger un endpoint selon la matrice RBAC.
    Utilisation :
        current_user: User = require_permission("pam", "read")
    """
    async def dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = (current_user.role or "").strip().lower()
        if not role_has_permission(user_role, module, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Accès refusé : module={module}, action={action}, "
                    f"rôle={user_role}"
                ),
            )
        return current_user

    return Depends(dependency)