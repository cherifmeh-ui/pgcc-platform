import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Response

from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints.auth import ConfirmMfaRequest, ChangePasswordRequiredResponse, ChangePasswordRequest
from app.core.security import decode_token
from app.services.mfa_encryption import MFA_SECRET_PREFIX


@pytest.mark.asyncio
async def test_mfa_returns_change_password_token_for_forced_password_change(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    user = MagicMock(
        email="forced@example.test",
        role="viewer",
        full_name="Forced User",
        is_active=True,
        is_locked=False,
        mfa_enabled=True,
        mfa_secret="totp-secret",
        must_change_password=True,
        failed_login_attempts=0,
        locked_until=None,
        last_login_at=None,
        backup_codes_hashed=[],
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: True)
    monkeypatch.setattr(auth_endpoint, "log_action", AsyncMock())
    monkeypatch.setattr(auth_endpoint, "enqueue_audit_event", AsyncMock())

    response = await auth_endpoint.confirm_mfa(
        payload=ConfirmMfaRequest(pre_auth_token="preauth", mfa_code="123456"),
        request=MagicMock(),
        response=Response(),
        db=db,
    )

    assert isinstance(response, ChangePasswordRequiredResponse)
    assert response.change_password_required is True
    assert response.user["must_change_password"] is True
    assert user.mfa_secret.startswith(MFA_SECRET_PREFIX)
    assert decode_token(response.change_password_token, expected_type="change_password")["sub"] == user.email
    assert not hasattr(response, "access_token")
    assert not hasattr(response, "refresh_token")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_initial_mfa_enrollment_returns_backup_codes_for_forced_password_change(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    backup_codes = ["ABCDE-12345", "FGHIJ-67890"]
    user = MagicMock(
        email="newuser@example.test",
        role="viewer",
        full_name="New User",
        is_active=True,
        is_locked=False,
        mfa_enabled=False,
        mfa_secret="totp-secret",
        must_change_password=True,
        failed_login_attempts=0,
        locked_until=None,
        last_login_at=None,
        backup_codes_hashed=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: True)
    monkeypatch.setattr(auth_endpoint, "generate_backup_codes", lambda count: backup_codes)
    monkeypatch.setattr(auth_endpoint, "hash_backup_codes", lambda codes: ["hashed"] * len(codes))
    monkeypatch.setattr(auth_endpoint, "log_action", AsyncMock())

    response = await auth_endpoint.confirm_mfa(
        payload=ConfirmMfaRequest(pre_auth_token="preauth", mfa_code="123456"),
        request=MagicMock(),
        response=Response(),
        db=db,
    )

    assert isinstance(response, ChangePasswordRequiredResponse)
    assert response.backup_codes == backup_codes
    assert user.mfa_enabled is True
    assert user.mfa_secret.startswith(MFA_SECRET_PREFIX)
    assert user.backup_codes_hashed == ["hashed", "hashed"]

@pytest.mark.asyncio
async def test_password_change_audit_is_enqueued_before_commit(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    from uuid import uuid4

    user = MagicMock(
        id=uuid4(), email="password-change@example.test", role="viewer",
        full_name="Password Change", is_active=True, must_change_password=True,
        password_hash="old-hash", password_changed_at=None, auth_version=0,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    order = []
    db = AsyncMock()
    db.execute.side_effect = lambda *args, **kwargs: order.append("execute") or result
    db.flush.side_effect = lambda: (order.append("flush"), setattr(user, "auth_version", user.auth_version + 1))
    db.commit.side_effect = lambda: order.append("commit")
    db.rollback.side_effect = lambda: order.append("rollback")
    issued_versions = []
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "hash_password", lambda password: "new-hash")
    monkeypatch.setattr(auth_endpoint, "create_access_token", lambda **kwargs: issued_versions.append(kwargs["auth_version"]) or "access")
    monkeypatch.setattr(auth_endpoint, "create_refresh_token", lambda **kwargs: "refresh")
    async def persist(*args, **kwargs):
        order.append("persist_refresh")
        return "refresh-hash"
    async def audit(*args, **kwargs):
        order.append("audit")
    monkeypatch.setattr(auth_endpoint, "_persist_refresh_session", persist)
    monkeypatch.setattr(auth_endpoint, "enqueue_audit_event", audit)

    http_response = Response()
    response = await auth_endpoint.change_password(
        ChangePasswordRequest(
            change_password_token="change-token", new_password="StrongPassword!123",
            confirm_password="StrongPassword!123",
        ), request=MagicMock(), response=http_response, db=db,
    )

    assert response.access_token == "access"
    assert issued_versions == [1]
    assert order.index("flush") < order.index("persist_refresh")
    assert not hasattr(response, "refresh_token")
    cookie = http_response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "pgcc_refresh=refresh" in cookie
    assert user.password_hash == "new-hash"
    assert user.must_change_password is False
    assert order.index("audit") < order.index("commit")
    assert order.index("persist_refresh") < order.index("audit")
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_change_rolls_back_if_audit_enqueue_fails(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    from uuid import uuid4

    user = MagicMock(
        id=uuid4(), email="password-rollback@example.test", role="viewer",
        full_name="Password Rollback", is_active=True, must_change_password=True,
        password_hash="old-hash", password_changed_at=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "hash_password", lambda password: "new-hash")
    monkeypatch.setattr(auth_endpoint, "create_access_token", lambda **kwargs: "access")
    monkeypatch.setattr(auth_endpoint, "create_refresh_token", lambda **kwargs: "refresh")
    monkeypatch.setattr(auth_endpoint, "_persist_refresh_session", AsyncMock())
    monkeypatch.setattr(
        auth_endpoint, "enqueue_audit_event",
        AsyncMock(side_effect=RuntimeError("simulated password audit failure")),
    )

    with pytest.raises(RuntimeError, match="simulated password audit failure"):
        await auth_endpoint.change_password(
            ChangePasswordRequest(
                change_password_token="change-token", new_password="StrongPassword!123",
                confirm_password="StrongPassword!123",
            ), request=MagicMock(), response=Response(), db=db,
        )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
