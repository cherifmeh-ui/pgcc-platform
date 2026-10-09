# backend/app/core/security.py
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
import jwt
import pyotp

from app.core.config import settings

_private_key: Optional[str] = None
_public_key: Optional[str] = None


def _read_key(path: str) -> str:
    if not path:
        raise ValueError("Chemin de clé JWT vide.")
    return Path(path).read_text(encoding="utf-8")


def get_signing_key() -> str:
    if settings.JWT_ALGORITHM == "HS256":
        return settings.JWT_SECRET
    global _private_key
    if _private_key is None:
        _private_key = _read_key(settings.JWT_PRIVATE_KEY_PATH)
    return _private_key


def get_verification_key() -> str:
    if settings.JWT_ALGORITHM == "HS256":
        return settings.JWT_SECRET
    global _public_key
    if _public_key is None:
        _public_key = _read_key(settings.JWT_PUBLIC_KEY_PATH)
    return _public_key


# ---------------- Mots de passe ----------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


# ---------------- JWT typés ----------------
def _create_token(
    subject: str | uuid.UUID,
    token_type: str,
    expires_minutes: int,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, get_signing_key(), algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject, role: str, extra_claims=None) -> str:
    return _create_token(
        subject, "access", settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        {"role": role, **(extra_claims or {})},
    )


def create_refresh_token(subject) -> str:
    return _create_token(subject, "refresh", settings.REFRESH_TOKEN_EXPIRE_DAYS * 1440)


def create_pre_auth_token(subject, role: str) -> str:
    return _create_token(
        subject, "pre_auth", settings.PRE_AUTH_TOKEN_EXPIRE_MINUTES, {"role": role}
    )


def create_change_password_token(subject, role: str) -> str:
    return _create_token(
        subject, "change_password", settings.CHANGE_PASSWORD_TOKEN_EXPIRE_MINUTES,
        {"role": role},
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    payload = jwt.decode(
        token, get_verification_key(), algorithms=[settings.JWT_ALGORITHM]
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Type de token invalide.")
    return payload


# ---------------- MFA ----------------
def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def get_mfa_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=email, issuer_name=settings.MFA_ISSUER_NAME
    )


def verify_mfa(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    cleaned = str(code).strip().replace(" ", "")
    if not cleaned.isdigit():
        return False
    # Fenetre courte : 1 par defaut (~ +/-30s), pilote par settings
    return pyotp.TOTP(secret).verify(cleaned, valid_window=settings.MFA_VALID_WINDOW)


def generate_backup_codes(count: int = 10) -> list[str]:
    alphabet = string.ascii_uppercase + string.digits
    out = []
    for _ in range(count):
        raw = "".join(secrets.choice(alphabet) for _ in range(10))
        out.append(f"{raw[:5]}-{raw[5:]}")
    return out


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [hash_password(c) for c in codes]


def verify_backup_code(code: str, hashed_codes: Optional[list[str]]) -> bool:
    if not code or not hashed_codes:
        return False
    cleaned = str(code).strip().upper()
    return any(verify_password(cleaned, h) for h in hashed_codes)