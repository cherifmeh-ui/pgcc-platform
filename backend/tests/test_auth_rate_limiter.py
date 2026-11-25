"""Unit tests for shared authentication rate-limit policy and keying."""
import pytest
from fastapi import HTTPException, Request
from cryptography.fernet import Fernet
from unittest.mock import AsyncMock

from app.core.config import Settings, settings
from app.services.auth_rate_limiter import (
    AUTH_RATE_LIMIT_POLICIES,
    enforce_auth_rate_limit,
    get_source_ip,
    rate_limit_bucket_key,
)


def test_all_auth_rate_limit_policies_have_bounded_positive_values():
    assert set(AUTH_RATE_LIMIT_POLICIES) == {
        "login",
        "mfa_confirm",
        "mfa_enrollment",
        "password_change",
        "refresh",
    }
    for action, scopes in AUTH_RATE_LIMIT_POLICIES.items():
        assert set(scopes) == {"ip", "account"}
        for limit, window_seconds, cooldown_seconds in scopes.values():
            assert limit > 1
            assert window_seconds > 0
            assert cooldown_seconds > 0


def test_rate_limit_bucket_keys_are_hmac_scoped_and_do_not_expose_identity(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_HMAC_KEY", "k" * 48)
    first = rate_limit_bucket_key("login:account", "User@Example.Test")
    normalized = rate_limit_bucket_key("login:account", "user@example.test")
    other_scope = rate_limit_bucket_key("mfa_confirm:account", "user@example.test")
    other_identity = rate_limit_bucket_key("login:account", "other@example.test")

    assert len(first) == 64
    assert first == normalized
    assert first != other_scope
    assert first != other_identity
    assert "user@example.test" not in first


@pytest.mark.asyncio
async def test_rate_limit_persistence_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_HMAC_KEY", "k" * 48)
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("database unavailable")
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [],
            "client": ("192.0.2.10", 1234),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )

    with pytest.raises(HTTPException) as denied:
        await enforce_auth_rate_limit(db, request, "login", subject="user@example.test")

    assert denied.value.status_code == 503
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


def test_untrusted_forwarded_header_is_ignored(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_IPS", "")
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [(b"x-forwarded-for", b"198.51.100.99")],
            "client": ("203.0.113.20", 1234),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    assert get_source_ip(request) == "203.0.113.20"


def test_forwarded_chain_is_resolved_only_through_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_IPS", "10.0.0.0/24")
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [(b"x-forwarded-for", b"198.51.100.7, 10.0.0.10")],
            "client": ("10.0.0.2", 1234),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    assert get_source_ip(request) == "198.51.100.7"


def test_malformed_forwarded_chain_falls_back_to_trusted_peer(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TRUSTED_PROXY_IPS", "10.0.0.0/24")
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [(b"x-forwarded-for", b"not-an-ip")],
            "client": ("10.0.0.2", 1234),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    assert get_source_ip(request) == "10.0.0.2"


def test_non_development_configuration_requires_dedicated_rate_limit_key():
    base = {
        "DATABASE_URL": "postgresql+asyncpg://pgcc:pgcc@localhost/pgcc",
        "JWT_SECRET": "s" * 48,
        "ENVIRONMENT": "staging",
        "MFA_ENCRYPTION_KEYS": Fernet.generate_key().decode("ascii"),
    }
    with pytest.raises(ValueError, match="AUTH_RATE_LIMIT_HMAC_KEY"):
        Settings(**base)

    configured = Settings(**base, AUTH_RATE_LIMIT_HMAC_KEY="r" * 48)
    assert configured.auth_rate_limit_hmac_key == "r" * 48

