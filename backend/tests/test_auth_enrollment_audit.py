import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints import auth as auth_endpoint
from app.services.mfa_encryption import MFA_SECRET_PREFIX, get_mfa_secret


@pytest.mark.asyncio
async def test_enrollment_audit_precedes_commit(monkeypatch):
    user = MagicMock(
        id="user-123", email="enrollment@example.test", mfa_enabled=False,
        is_active=True, mfa_secret=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    order = []
    db = AsyncMock()
    db.execute.side_effect = lambda *args, **kwargs: order.append("select") or result
    db.commit.side_effect = lambda: order.append("commit")
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email})
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
    user = MagicMock(
        id="user-456", email="enrollment-failure@example.test", mfa_enabled=False,
        is_active=True, mfa_secret=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"sub": user.email})
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
