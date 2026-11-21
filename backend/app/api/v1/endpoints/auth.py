# backend/app/api/v1/endpoints/auth.py
from datetime import datetime, timedelta, timezone
import hashlib
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
from app.models.refresh_token_session import RefreshTokenSession
from app.services.security_logger import log_action
from app.services.auth_session_policy import refresh_denial_reason

router = APIRouter(prefix="/auth", tags=["Authentification"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)


class PreAuthTokenResponse(BaseModel):
    mfa_required: bool
    pre_auth_token: str
    email: str
    mfa_enabled: bool


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


class ChangePasswordRequiredResponse(BaseModel):
    change_password_required: bool = True
    change_password_token: str
    backup_codes: list[str] = Field(default_factory=list)
    user: dict


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


def _now():
    return datetime.now(timezone.utc)


def _refresh_jti_hash(token_data: dict) -> str:
    jti = token_data.get("jti")
    if not isinstance(jti, str) or not jti:
        raise HTTPException(status_code=401, detail="Refresh token invalide.")
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


async def _persist_refresh_session(db: AsyncSession, user: User, token: str) -> str:
    token_data = decode_token(token, expected_type="refresh")
    token_hash = _refresh_jti_hash(token_data)
    expires_epoch = token_data.get("exp")
    if isinstance(expires_epoch, bool) or not isinstance(expires_epoch, (int, float)):
        raise HTTPException(status_code=401, detail="Refresh token invalide.")
    expires_at = datetime.fromtimestamp(expires_epoch, tz=timezone.utc)
    db.add(RefreshTokenSession(user_id=user.id, token_jti_hash=token_hash, expires_at=expires_at))
    return token_hash


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

    result = await db.execute(select(User).where(User.email == email).with_for_update())
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
        mfa_enabled=user.mfa_enabled,
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


@router.post("/confirm-mfa", response_model=TokenPairResponse | ChangePasswordRequiredResponse)
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

    # Lock the user row during MFA verification so a recovery code cannot be
    # consumed concurrently by two requests (one-time-use guarantee).
    result = await db.execute(
        select(User).where(User.email == email).with_for_update()
    )
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
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Compte temporairement verrouillé après plusieurs échecs MFA.",
        )

    valid_totp = verify_mfa(user.mfa_secret, payload.mfa_code)
    remaining_backup_codes = None
    if not valid_totp and user.mfa_enabled:
        remaining_backup_codes = consume_backup_code(payload.mfa_code, user.backup_codes_hashed)

    if not valid_totp and remaining_backup_codes is None:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        locked = user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS
        if locked:
            user.locked_until = _now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            user.failed_login_attempts = 0
        await db.commit()
        await log_action(
            user_email=user.email,
            action="MFA_FAILED",
            resource="auth",
            details="Code MFA invalide" + ("; compte verrouillé temporairement" if locked else ""),
            event_type="AUTH",
            request=request,
        )
        if locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Compte temporairement verrouillé après plusieurs échecs MFA.",
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

    if user.must_change_password:
        change_password_token = create_change_password_token(subject=user.email, role=user.role)
        await log_action(
            user_email=user.email,
            action="MFA_SUCCESS_PASSWORD_CHANGE_REQUIRED",
            resource="auth",
            details="MFA réussi; changement obligatoire du mot de passe requis",
            event_type="AUTH",
            request=request,
        )
        return ChangePasswordRequiredResponse(
            change_password_token=change_password_token,
            backup_codes=backup_codes,
            user={
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "must_change_password": True,
                "mfa_enabled": True,
            },
        )

    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)
    await _persist_refresh_session(db, user, refresh_token)
    await db.commit()

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
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")

    email = data.get("sub")
    result = await db.execute(select(User).where(User.email == email).with_for_update())
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé.")
    if not user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="Ce token est réservé au changement obligatoire du mot de passe.",
        )

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = _now()

    # Password changes invalidate all previously issued refresh sessions.
    await db.execute(
        update(RefreshTokenSession)
        .where(RefreshTokenSession.user_id == user.id, RefreshTokenSession.revoked_at.is_(None))
        .values(revoked_at=user.password_changed_at)
    )

    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)
    await _persist_refresh_session(db, user, refresh_token)

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
    """Rotate a persisted refresh session exactly once; reject replay."""
    try:
        data = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalide ou expiré.")

    email = data.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token invalide.")

    result = await db.execute(select(User).where(User.email == email).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé.")

    denial_reason = refresh_denial_reason(
        is_active=user.is_active,
        is_locked=user.is_locked,
        must_change_password=user.must_change_password,
        role=user.role,
        mfa_enabled=user.mfa_enabled,
        password_changed_at=user.password_changed_at,
        token_issued_at=data.get("iat"),
    )
    if denial_reason:
        # Revoke all sessions when the account is no longer eligible to refresh.
        await db.execute(
            update(RefreshTokenSession)
            .where(RefreshTokenSession.user_id == user.id, RefreshTokenSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
        await db.commit()
        denial_status = status.HTTP_423_LOCKED if user.is_locked else status.HTTP_403_FORBIDDEN if not user.is_active or user.must_change_password else status.HTTP_401_UNAUTHORIZED
        raise HTTPException(status_code=denial_status, detail=denial_reason)

    token_hash = _refresh_jti_hash(data)
    session_result = await db.execute(
        select(RefreshTokenSession).where(RefreshTokenSession.token_jti_hash == token_hash).with_for_update()
    )
    session = session_result.scalar_one_or_none()
    now = _now()
    if session is None or session.user_id != user.id or session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Session refresh invalide ou expirée.")
    if session.revoked_at is not None:
        # Reuse of a revoked token revokes the user's active refresh sessions.
        await db.execute(
            update(RefreshTokenSession)
            .where(RefreshTokenSession.user_id == user.id, RefreshTokenSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Réutilisation d'un refresh token détectée. Sessions révoquées.")

    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)
    new_hash = await _persist_refresh_session(db, user, refresh_token)
    session.revoked_at = now
    session.replaced_by_jti_hash = new_hash
    await db.commit()

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"email": user.email, "full_name": user.full_name, "role": user.role,
              "must_change_password": user.must_change_password, "mfa_enabled": user.mfa_enabled},
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Revoke the presented refresh session; idempotent for invalid/revoked tokens."""
    try:
        data = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception:
        return None
    token_hash = _refresh_jti_hash(data)
    await db.execute(
        update(RefreshTokenSession)
        .where(RefreshTokenSession.token_jti_hash == token_hash, RefreshTokenSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.commit()
    return None
