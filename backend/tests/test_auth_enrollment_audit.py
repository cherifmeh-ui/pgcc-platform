import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints import auth as auth_endpoint
from app.services.mfa_encryption import MFA_SECRET_PREFIX, get_mfa_secret


@pytest.mark.asyncio
async def test_enrollment_audit_precedes_commit(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    user = MagicMock(
        id="user-123", email="enrollment@example.test", role="viewer", auth_version=0, mfa_enabled=False,
        is_active=True, mfa_secret=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    order = []
    db = AsyncMock()
    db.execute.side_effect = lambda *args, **kwargs: order.append("select") or result
    db.commit.side_effect = lambda: order.append("commit")
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "generate_mfa_secret", lambda: "TEST-SECRET")
    monkeypatch.setattr(auth_endpoint, "get_mfa_uri", lambda secret, email: "otpauth://test")

    async def audit(*args, **kwargs):
        order.append("audit")

    monkeypatch.setattr(auth_endpoint, "enqueue_audit_event", audit)
    response = await auth_endpoint.start_enrollment(
        request=MagicMock(), credentials="token-placeholder", db=db,
    )
    assert response.secret == "TEST-SECRET"
    assert user.mfa_secret.startswith(MFA_SECRET_PREFIX)
    assert get_mfa_secret(user) == response.secret
    assert order.index("audit") < order.index("commit")
    assert order.index("select") < order.index("audit")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrollment_rolls_back_when_audit_fails(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    user = MagicMock(
        id="user-456", email="enrollment-failure@example.test", role="viewer", auth_version=0, mfa_enabled=False,
        is_active=True, mfa_secret=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "generate_mfa_secret", lambda: "TEST-SECRET")
    monkeypatch.setattr(
        auth_endpoint, "enqueue_audit_event",
        AsyncMock(side_effect=RuntimeError("audit unavailable")),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await auth_endpoint.start_enrollment(
            request=MagicMock(), credentials="token-placeholder", db=db,
        )
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_mfa_enrollment_token_uses_bumped_auth_version(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    from fastapi import Response

    user = MagicMock(
        id="user-789", email="mfa-version@example.test", role="viewer",
        full_name="MFA Version", is_active=True, is_locked=False,
        mfa_enabled=False, mfa_secret="totp-secret", must_change_password=False,
        failed_login_attempts=0, locked_until=None, last_login_at=None,
        backup_codes_hashed=None, auth_version=0,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result

    async def flush_and_bump_version():
        user.auth_version += 1

    db.flush.side_effect = flush_and_bump_version
    issued_versions = []
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email, "role": user.role, "auth_version": int(user.auth_version or 0)})
    monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: True)
    monkeypatch.setattr(auth_endpoint, "generate_backup_codes", lambda count: ["BACKUP-CODE"])
    monkeypatch.setattr(auth_endpoint, "hash_backup_codes", lambda codes: ["hashed"])
    monkeypatch.setattr(
        auth_endpoint, "create_access_token",
        lambda **kwargs: issued_versions.append(kwargs["auth_version"]) or "access-token",
    )
    monkeypatch.setattr(auth_endpoint, "create_refresh_token", lambda **kwargs: "refresh-token")
    monkeypatch.setattr(auth_endpoint, "_persist_refresh_session", AsyncMock())
    monkeypatch.setattr(auth_endpoint, "enqueue_audit_event", AsyncMock())

    response = await auth_endpoint.confirm_mfa(
        payload=auth_endpoint.ConfirmMfaRequest(pre_auth_token="preauth", mfa_code="123456"),
        request=MagicMock(), response=Response(), db=db,
    )

    assert response.access_token == "access-token"
    assert issued_versions == [1]
    assert user.auth_version == 1
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("flow", ["enrollment", "confirmation", "password_change"])
@pytest.mark.parametrize("stale_claim", ["version", "role", "missing_version"])
async def test_stale_workflow_token_is_rejected_after_security_version_change(monkeypatch, flow, stale_claim):
    from fastapi import Response, HTTPException

    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    user = MagicMock(
        id="user-stale", email="stale@example.test", role="viewer",
        auth_version=2, is_active=True, is_locked=False, mfa_enabled=False,
        mfa_secret="encrypted-placeholder", must_change_password=True,
        failed_login_attempts=0, locked_until=None, backup_codes_hashed=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(
        auth_endpoint, "decode_token",
        lambda token, expected_type: {
            "sub": user.email,
            "role": "auditor" if stale_claim == "role" else user.role,
            "auth_version": None if stale_claim == "missing_version" else (
                1 if stale_claim == "version" else user.auth_version
            ),
        },
    )

    with pytest.raises(HTTPException) as denied:
        if flow == "enrollment":
            await auth_endpoint.start_enrollment(
                request=MagicMock(), credentials="Bearer stale-token", db=db,
            )
        elif flow == "confirmation":
            await auth_endpoint.confirm_mfa(
                payload=auth_endpoint.ConfirmMfaRequest(
                    pre_auth_token="stale-token", mfa_code="123456",
                ),
                request=MagicMock(), response=Response(), db=db,
            )
        else:
            await auth_endpoint.change_password(
                auth_endpoint.ChangePasswordRequest(
                    change_password_token="stale-token",
                    new_password="StrongPassword!123",
                    confirm_password="StrongPassword!123",
                ),
                request=MagicMock(), response=Response(), db=db,
            )

    assert denied.value.status_code == 401
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("flow", ["login", "mfa"])
@pytest.mark.parametrize("audit_fails", [False, True])
async def test_failed_authentication_state_and_audit_share_one_transaction(monkeypatch, flow, audit_fails):
    from fastapi import HTTPException, Response

    user = MagicMock(
        id="user-failed-auth", email="failed-auth@example.com", role="viewer",
        auth_version=0, is_active=True, is_locked=False, mfa_enabled=False,
        mfa_secret="encrypted-placeholder", failed_login_attempts=0,
        locked_until=None, backup_codes_hashed=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    order = []
    db = AsyncMock()
    db.execute.return_value = result
    db.commit.side_effect = lambda: order.append("commit")

    async def audit(*args, **kwargs):
        order.append("audit")
        if audit_fails:
            raise RuntimeError("audit outbox unavailable")

    monkeypatch.setattr(auth_endpoint, "enqueue_audit_event", audit)
    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    if flow == "login":
        monkeypatch.setattr(auth_endpoint, "verify_password", lambda password, hashed: False)
        invoke = lambda: auth_endpoint.login(
            auth_endpoint.LoginRequest(email=user.email, password="wrong-password"),
            request=MagicMock(), db=db,
        )
    else:
        monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {
            "sub": user.email, "role": user.role, "auth_version": 0,
        })
        monkeypatch.setattr(auth_endpoint, "get_mfa_secret", lambda account: "test-secret")
        monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: False)
        invoke = lambda: auth_endpoint.confirm_mfa(
            payload=auth_endpoint.ConfirmMfaRequest(
                pre_auth_token="preauth", mfa_code="000000",
            ),
            request=MagicMock(), response=Response(), db=db,
        )

    if audit_fails:
        with pytest.raises(RuntimeError, match="audit outbox unavailable"):
            await invoke()
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()
        assert order == ["audit"]
    else:
        with pytest.raises(HTTPException) as denied:
            await invoke()
        assert denied.value.status_code == 401
        assert order == ["audit", "commit"]
        db.rollback.assert_not_awaited()
