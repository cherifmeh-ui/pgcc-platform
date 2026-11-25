"""Application-level encryption for persisted TOTP secrets.

MFA_ENCRYPTION_KEYS is a comma-separated Fernet key ring. The first key is
active for new ciphertext; remaining keys are retained temporarily to decrypt
and lazily rotate older ciphertext during a key rotation.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

MFA_SECRET_PREFIX = "fernet:v1:"


class MFASecretDecryptionError(RuntimeError):
    """Raised when a persisted MFA secret cannot be decrypted with the key ring."""


def _key_ring() -> list[Fernet]:
    keys = settings.mfa_encryption_keys
    if not keys:
        raise RuntimeError("MFA encryption key ring is not configured.")
    try:
        return [Fernet(key.encode("ascii")) for key in keys]
    except Exception as exc:
        raise RuntimeError("MFA encryption key ring contains an invalid Fernet key.") from exc


def encrypt_mfa_secret(secret: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise ValueError("A non-empty MFA secret is required.")
    active = _key_ring()[0]
    return MFA_SECRET_PREFIX + active.encrypt(secret.encode("utf-8")).decode("ascii")


def get_mfa_secret(user) -> str | None:
    """Return plaintext for TOTP verification while migrating/rotating at rest."""
    stored = getattr(user, "mfa_secret", None)
    if not stored:
        return None

    key_ring = _key_ring()
    if not stored.startswith(MFA_SECRET_PREFIX):
        # Legacy plaintext rows are transparently encrypted on first MFA use.
        user.mfa_secret = encrypt_mfa_secret(stored)
        return stored

    token = stored[len(MFA_SECRET_PREFIX):].encode("ascii")
    for index, key in enumerate(key_ring):
        try:
            plaintext = key.decrypt(token).decode("utf-8")
        except InvalidToken:
            continue
        except (UnicodeDecodeError, ValueError) as exc:
            raise MFASecretDecryptionError("Stored MFA secret is malformed.") from exc

        if index > 0:
            # A previous key decrypted this value: rotate it to the active key.
            user.mfa_secret = encrypt_mfa_secret(plaintext)
        return plaintext

    raise MFASecretDecryptionError("Stored MFA secret cannot be decrypted with the configured key ring.")
