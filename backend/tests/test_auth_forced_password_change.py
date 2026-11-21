import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints.auth import ConfirmMfaRequest, ChangePasswordRequiredResponse
from app.core.security import decode_token


@pytest.mark.asyncio
async def test_mfa_returns_change_password_token_for_forced_password_change(monkeypatch):
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
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email})
    monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: True)
    monkeypatch.setattr(auth_endpoint, "log_action", AsyncMock())

    response = await auth_endpoint.confirm_mfa(
        payload=ConfirmMfaRequest(pre_auth_token="preauth", mfa_code="123456"),
        request=MagicMock(),
        db=db,
    )

    assert isinstance(response, ChangePasswordRequiredResponse)
    assert response.change_password_required is True
    assert response.user["must_change_password"] is True
    assert decode_token(response.change_password_token, expected_type="change_password")["sub"] == user.email
    assert not hasattr(response, "access_token")
    assert not hasattr(response, "refresh_token")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_initial_mfa_enrollment_returns_backup_codes_for_forced_password_change(monkeypatch):
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
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email})
    monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: True)
    monkeypatch.setattr(auth_endpoint, "generate_backup_codes", lambda count: backup_codes)
    monkeypatch.setattr(auth_endpoint, "hash_backup_codes", lambda codes: ["hashed"] * len(codes))
    monkeypatch.setattr(auth_endpoint, "log_action", AsyncMock())

    response = await auth_endpoint.confirm_mfa(
        payload=ConfirmMfaRequest(pre_auth_token="preauth", mfa_code="123456"),
        request=MagicMock(),
        db=db,
    )

    assert isinstance(response, ChangePasswordRequiredResponse)
    assert response.backup_codes == backup_codes
    assert user.mfa_enabled is True
    assert user.backup_codes_hashed == ["hashed", "hashed"]
