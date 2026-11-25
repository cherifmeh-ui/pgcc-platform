"""Administration sécurisée du cycle de vie des comptes utilisateurs."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.refresh_token_session import RefreshTokenSession
from app.models.user import User
from app.services.security_logger import enqueue_audit_event

router = APIRouter(prefix="/admin/users", tags=["Administration des comptes"])

_ALLOWED_ROLES = {"admin", "executive", "auditor", "viewer"}


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    department: str | None
    role: str
    is_active: bool
    mfa_enabled: bool
    must_change_password: bool
    auth_version: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Le nom complet ne peut pas être vide.")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_ROLES:
            raise ValueError("Rôle utilisateur non autorisé.")
        return normalized

    @field_validator("department")
    @classmethod
    def normalize_department(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    limit: int
    offset: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _lock_active_mfa_admins(db: AsyncSession) -> list[User]:
    """Sérialise les mutations qui peuvent réduire le nombre d'admins MFA actifs."""
    result = await db.execute(
        select(User)
        .where(
            func.lower(func.trim(User.role)) == "admin",
            User.is_active.is_(True),
            User.mfa_enabled.is_(True),
        )
        .order_by(User.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def _lock_authorized_admin(
    db: AsyncSession,
    current_user: User,
    locked_admins: list[User],
    expected_auth_version: int,
) -> User:
    """Revalidate the actor under the same locks to prevent stale-admin TOCTOU."""
    actor = next((user for user in locked_admins if user.id == current_user.id), None)
    if actor is None:
        result = await db.execute(
            select(User)
            .where(User.id == current_user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        actor = result.scalar_one_or_none()
    if (
        actor is None
        or not actor.is_active
        or (actor.role or "").strip().lower() != "admin"
        or not actor.mfa_enabled
        or int(actor.auth_version or 0) != expected_auth_version
    ):
        raise HTTPException(
            status_code=403,
            detail="Droits administrateur ou état de sécurité modifiés. Reconnectez-vous.",
        )
    return actor


async def _lock_target_user(
    db: AsyncSession, user_id: UUID, locked_admins: list[User]
) -> User:
    target = next((user for user in locked_admins if user.id == user_id), None)
    if target is not None:
        return target
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return target


async def _revoke_refresh_sessions(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        update(RefreshTokenSession)
        .where(
            RefreshTokenSession.user_id == user_id,
            RefreshTokenSession.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )
    return int(result.rowcount or 0)


async def _audit(
    db: AsyncSession,
    request: Request,
    actor: User,
    target: User,
    action: str,
    details: str,
) -> None:
    await enqueue_audit_event(
        db,
        user_email=actor.email,
        action=action,
        resource="users",
        resource_id=str(target.id),
        details=details,
        event_type="AUTH",
        request=request,
    )


@router.get("/", response_model=AdminUserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("users", "manage"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    total = await db.scalar(select(func.count()).select_from(User))
    result = await db.execute(
        select(User).order_by(User.created_at.desc(), User.id).offset(offset).limit(limit)
    )
    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(user) for user in result.scalars().all()],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("users", "manage"),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return AdminUserResponse.model_validate(target)


@router.patch("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("users", "manage"),
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Aucune modification fournie.")
    if any(value is None for key, value in changes.items() if key in {"full_name", "role", "is_active"}):
        raise HTTPException(status_code=422, detail="Un champ obligatoire ne peut pas être nul.")

    try:
        expected_auth_version = int(current_user.auth_version or 0)
        locked_admins = await _lock_active_mfa_admins(db)
        await _lock_authorized_admin(
            db, current_user, locked_admins, expected_auth_version
        )
        target = await _lock_target_user(db, user_id, locked_admins)

        if target.id == current_user.id and (
            changes.get("is_active") is False
            or ("role" in changes and changes["role"] != "admin")
        ):
            raise HTTPException(
                status_code=409,
                detail="Un administrateur ne peut pas désactiver son propre compte ni retirer ses privilèges.",
            )

        loses_admin_mfa = (
            target in locked_admins
            and (
                changes.get("is_active") is False
                or ("role" in changes and changes["role"] != "admin")
            )
        )
        if loses_admin_mfa and len(locked_admins) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Impossible de retirer le dernier compte administrateur actif avec MFA.",
            )

        before = {
            key: getattr(target, key)
            for key in changes
        }
        for key, value in changes.items():
            setattr(target, key, value)

        security_changed = any(
            key in {"role", "is_active"} and before[key] != changes[key]
            for key in changes
        )
        revoked = await _revoke_refresh_sessions(db, target.id) if security_changed else 0
        await _audit(
            db, request, current_user, target, "ADMIN_USER_UPDATED",
            f"Champs modifiés: {', '.join(sorted(changes))}; sessions révoquées: {revoked}",
        )
        await db.flush()
        await db.commit()
        await db.refresh(target)
        return AdminUserResponse.model_validate(target)
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise


@router.post("/{user_id}/mfa/reset", response_model=AdminUserResponse)
async def reset_user_mfa(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("users", "manage"),
):
    try:
        expected_auth_version = int(current_user.auth_version or 0)
        locked_admins = await _lock_active_mfa_admins(db)
        await _lock_authorized_admin(
            db, current_user, locked_admins, expected_auth_version
        )
        target = await _lock_target_user(db, user_id, locked_admins)
        if target.id == current_user.id:
            raise HTTPException(status_code=409, detail="Un administrateur ne peut pas réinitialiser son propre MFA.")
        if target in locked_admins and len(locked_admins) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Impossible de réinitialiser le MFA du dernier administrateur actif.",
            )

        auth_version_before_reset = int(target.auth_version or 0)
        target.mfa_enabled = False
        target.mfa_secret = None
        target.mfa_confirmed_at = None
        target.backup_codes_hashed = None
        # The model hook bumps auth_version when enabled/confirmed MFA changes.
        # Also invalidate access tokens when cleaning stale MFA material from an
        # account whose MFA was already disabled.
        await db.flush()
        if int(target.auth_version or 0) == auth_version_before_reset:
            target.auth_version = auth_version_before_reset + 1
        revoked = await _revoke_refresh_sessions(db, target.id)
        await _audit(
            db, request, current_user, target, "ADMIN_USER_MFA_RESET",
            f"MFA réinitialisé ; sessions de renouvellement révoquées: {revoked}",
        )
        await db.flush()
        await db.commit()
        await db.refresh(target)
        return AdminUserResponse.model_validate(target)
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise


@router.post("/{user_id}/sessions/revoke", response_model=AdminUserResponse)
async def revoke_user_sessions(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("users", "manage"),
):
    try:
        expected_auth_version = int(current_user.auth_version or 0)
        locked_admins = await _lock_active_mfa_admins(db)
        await _lock_authorized_admin(
            db, current_user, locked_admins, expected_auth_version
        )
        target = await _lock_target_user(db, user_id, locked_admins)
        revoked = await _revoke_refresh_sessions(db, target.id)
        # Invalidate access tokens as well; this field is intentionally managed
        # explicitly because the model hook tracks account-field changes.
        target.auth_version = int(target.auth_version or 0) + 1
        await _audit(
            db, request, current_user, target, "ADMIN_USER_SESSIONS_REVOKED",
            f"Sessions de renouvellement révoquées: {revoked}; sessions d'accès invalidées.",
        )
        await db.flush()
        await db.commit()
        await db.refresh(target)
        return AdminUserResponse.model_validate(target)
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
