# backend/app/api/v1/endpoints/auth.py
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
#                                                    ^^^^^^^ AJOUTÉ
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_change_password_token,
    create_pre_auth_token,
    create_refresh_token,
    decode_token,
    generate_backup_codes,
    generate_mfa_secret,
    get_mfa_uri,
    hash_backup_codes,
    hash_password,
    verify_backup_code,
    consume_backup_code,
    verify_mfa,
    verify_password,
)
from app.models.user import User
from app.services.security_logger import log_action

router = APIRouter(prefix="/auth", tags=["Authentification"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)


class PreAuthTokenResponse(BaseModel):
    mfa_required: bool
    pre_auth_token: str
    email: str


class StartEnrollmentResponse(BaseModel):
    secret: str
    provisioning_uri: str
    message: str


class ConfirmMfaRequest(BaseModel):
    pre_auth_token: str
    mfa_code: str = Field(min_length=6, max_length=32)


class ChangePasswordRequest(BaseModel):
    change_password_token: str
    new_password: str = Field(min_length=12, max_length=255)
    confirm_password: str = Field(min_length=12, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


def _now():
    return datetime.now(timezone.utc)


@router.post("/login", response_model=PreAuthTokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Étape 1 : vérification email + mot de passe.
    Retourne un pre_auth_token si le mot de passe est correct.
    """
    email = payload.email.lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        await log_action(
            user_email=email,
            action="LOGIN_FAILED",
            resource="auth",
            details="Utilisateur inconnu ou mot de passe incorrect",
            event_type="AUTH",
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    if user.is_locked:
        await log_action(
            user_email=user.email,
            action="LOGIN_BLOCKED",
            resource="auth",
            details="Compte temporairement verrouillé",
            event_type="AUTH",
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Compte temporairement verrouillé. Réessayez plus tard.",
        )

    if not user.is_active:
        await log_action(
            user_email=user.email,
            action="LOGIN_FAILED",
            resource="auth",
            details="Compte désactivé",
            event_type="AUTH",
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = _now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            user.failed_login_attempts = 0

        await db.commit()

        await log_action(
            user_email=user.email,
            action="LOGIN_FAILED",
            resource="auth",
            details="Mot de passe incorrect",
            event_type="AUTH",
            request=request,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    pre_auth_token = create_pre_auth_token(subject=user.email, role=user.role)

    await log_action(
        user_email=user.email,
        action="PASSWORD_OK",
        resource="auth",
        details="Vérification mot de passe réussie, MFA requis",
        event_type="AUTH",
        request=request,
    )

    return PreAuthTokenResponse(
        mfa_required=True,
        pre_auth_token=pre_auth_token,
        email=user.email,
    )


@router.post("/start-enrollment", response_model=StartEnrollmentResponse)
async def start_enrollment(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: str = Header(..., alias="Authorization"), # Expecting Bearer <pre_auth_token>
):
    """
    Démarre l'enrôlement MFA pour un utilisateur pré-authentifié.
    Génère un secret, le sauvegarde sur l'user (sans activer MFA), et retourne l'URI QR.
    """
    token = credentials.replace("Bearer ", "")
    try:
        data = decode_token(token, expected_type="pre_auth")
    except Exception:
        raise HTTPException(status_code=401, detail="Pre-auth token invalide.")

    email = data.get("sub")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé.")

    # Enrôlement uniquement pour les comptes sans MFA actif.
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA déjà activé.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé.")

    secret = generate_mfa_secret()
    user.mfa_secret = secret
    await db.commit()

    uri = get_mfa_uri(secret, user.email)

    return StartEnrollmentResponse(
        secret=secret,
        provisioning_uri=uri,
        message="Scannez ce QR code avec votre authenticator, puis appelez /confirm-mfa."
    )


@router.post("/confirm-mfa", response_model=TokenPairResponse)
async def confirm_mfa(
    payload: ConfirmMfaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Valide le code TOTP contre le secret généré précédemment.
    Active définitivement le MFA, génère les codes de secours, et délivre les tokens finaux.
    """
    try:
        data = decode_token(payload.pre_auth_token, expected_type="pre_auth")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton de pré-authentification invalide ou expiré.",
        )

    email = data.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Jeton invalide.")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé.")

    if not user.mfa_secret:
        raise HTTPException(
            status_code=400,
            detail="Aucune procédure d'enrôlement MFA active. Appelez /start-enrollment d'abord.",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé.")

    valid_totp = verify_mfa(user.mfa_secret, payload.mfa_code)
    remaining_backup_codes = None
    if not valid_totp and user.mfa_enabled:
        remaining_backup_codes = consume_backup_code(payload.mfa_code, user.backup_codes_hashed)

    if not valid_totp and remaining_backup_codes is None:
        await log_action(
            user_email=user.email,
            action="MFA_FAILED",
            resource="auth",
            details="Code MFA invalide lors de la confirmation",
            event_type="AUTH",
            request=request,
        )
        raise HTTPException(status_code=401, detail="Code MFA invalide.")

    # MFA existant : un code de secours consommé ne doit jamais être réutilisable.
    if user.mfa_enabled and remaining_backup_codes is not None:
        user.backup_codes_hashed = remaining_backup_codes

    # Enrôlement initial : activer MFA et générer les codes de secours une seule fois.
    backup_codes = []
    if not user.mfa_enabled:
        backup_codes = generate_backup_codes(10)
        user.backup_codes_hashed = hash_backup_codes(backup_codes)
        user.mfa_enabled = True
        user.mfa_confirmed_at = _now()

    user.last_login_at = _now()
    user.failed_login_attempts = 0
    user.locked_until = None

    await db.commit()

    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)

    await log_action(
        user_email=user.email,
        action="MFA_ENROLLED_AND_LOGIN_SUCCESS",
        resource="auth",
        details="MFA activé et connexion réussie",
        event_type="AUTH",
        request=request,
    )

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "must_change_password": user.must_change_password,
            "mfa_enabled": True,
            **({"backup_codes": backup_codes} if backup_codes else {}), # Initial enrollment only
        }
    )


@router.post("/change-password", response_model=TokenPairResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Permet à un utilisateur contraint de changer son mot de passe.
    Utilise le change_password_token délivré après MFA si must_change_password était true.
    """
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Les mots de passe ne correspondent pas.",
        )

    try:
        data = decode_token(payload.change_password_token, expected_type="change_password")
    except Exception:
        # Fallback : tenter de décoder comme access token (cas où user est déjà connecté mais veut changer mdp)
        try:
             data = decode_token(payload.change_password_token, expected_type="access")
        except:
             raise HTTPException(status_code=401, detail="Token invalide ou expiré.")

    email = data.get("sub")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé.")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = _now()

    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)

    await db.commit()

    await log_action(
        user_email=user.email,
        action="PASSWORD_CHANGED",
        resource="auth",
        details="Mot de passe changé avec succès",
        event_type="AUTH",
        request=request,
    )

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "must_change_password": False,
            "mfa_enabled": user.mfa_enabled,
        }
    )


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_tokens(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Échange un refresh_token valide contre un nouvel access_token + refresh_token.
    """
    try:
        data = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré.",
        )

    email = data.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token invalide.")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé.")

    # Revoke refresh tokens issued before the last password change.
    password_changed_at = user.password_changed_at
    token_issued_at = data.get("iat")
    if password_changed_at and token_issued_at:
        issued = datetime.fromtimestamp(token_issued_at, tz=timezone.utc)
        if issued < password_changed_at:
            raise HTTPException(status_code=401, detail="Refresh token révoqué.")

    # Régénérer les tokens
    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "must_change_password": user.must_change_password,
            "mfa_enabled": user.mfa_enabled,
        }
    )