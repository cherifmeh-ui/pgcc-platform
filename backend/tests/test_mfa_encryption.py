from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services.mfa_encryption import (
    MFA_SECRET_PREFIX,
    MFASecretDecryptionError,
    encrypt_mfa_secret,
    get_mfa_secret,
)


def test_mfa_secret_is_encrypted_at_rest_and_decrypted_for_verification():
    secret = "JBSWY3DPEHPK3PXP"
    user = SimpleNamespace(mfa_secret=encrypt_mfa_secret(secret))
    stored = user.mfa_secret

    assert stored.startswith(MFA_SECRET_PREFIX)
    assert secret not in stored
    assert get_mfa_secret(user) == secret
    assert user.mfa_secret == stored


def test_legacy_plaintext_secret_is_lazily_encrypted():
    user = SimpleNamespace(mfa_secret="LEGACY-TOTP-SECRET")
    assert get_mfa_secret(user) == "LEGACY-TOTP-SECRET"
    assert user.mfa_secret.startswith(MFA_SECRET_PREFIX)
    assert "LEGACY-TOTP-SECRET" not in user.mfa_secret


def test_old_key_secret_is_rotated_to_active_key(monkeypatch):
    old_key = Fernet.generate_key()
    new_key = Fernet.generate_key()
    monkeypatch.setattr(settings, "MFA_ENCRYPTION_KEYS", f"{new_key.decode()},{old_key.decode()}")
    old_token = Fernet(old_key).encrypt(b"ROTATE-ME").decode()
    user = SimpleNamespace(mfa_secret=MFA_SECRET_PREFIX + old_token)

    assert get_mfa_secret(user) == "ROTATE-ME"
    rotated_token = user.mfa_secret.removeprefix(MFA_SECRET_PREFIX).encode()
    assert Fernet(new_key).decrypt(rotated_token) == b"ROTATE-ME"
    assert rotated_token != old_token.encode()


def test_undecryptable_mfa_secret_fails_closed(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "MFA_ENCRYPTION_KEYS", key)
    user = SimpleNamespace(mfa_secret=MFA_SECRET_PREFIX + Fernet.generate_key().decode())

    with pytest.raises(MFASecretDecryptionError):
        get_mfa_secret(user)


def test_non_development_settings_require_a_managed_mfa_key_ring():
    common = {
        "DATABASE_URL": "postgresql+asyncpg://pgcc:secret@localhost/pgcc",
        "JWT_SECRET": "S" * 64,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "CORS_ORIGINS": "https://pgcc.example",
    }
    with pytest.raises(ValidationError, match="MFA_ENCRYPTION_KEYS"):
        Settings(**common)

    valid_key = Fernet.generate_key().decode()
    configured = Settings(**common, MFA_ENCRYPTION_KEYS=valid_key)
    assert configured.mfa_encryption_keys == [valid_key]


def test_development_key_derivation_is_deterministic_and_not_the_jwt_secret():
    first = Settings(
        DATABASE_URL="postgresql+asyncpg://pgcc:secret@localhost/pgcc",
        JWT_SECRET="D" * 64,
        ENVIRONMENT="development",
    )
    second = Settings(
        DATABASE_URL="postgresql+asyncpg://pgcc:secret@localhost/pgcc",
        JWT_SECRET="D" * 64,
        ENVIRONMENT="development",
    )
    assert first.mfa_encryption_keys == second.mfa_encryption_keys
    assert first.mfa_encryption_keys[0] != first.JWT_SECRET
    assert len(first.mfa_encryption_keys[0]) == 44
