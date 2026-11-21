import pytest
from unittest.mock import AsyncMock

from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints.auth import RefreshRequest


@pytest.mark.asyncio
async def test_logout_invalid_token_is_idempotent(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: (_ for _ in ()).throw(ValueError("invalid")))
    result = await auth_endpoint.logout(RefreshRequest(refresh_token="invalid"), db)
    assert result is None
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_revokes_refresh_session_by_jti_hash(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"jti": "logout-jti", "type": expected_type})
    result = await auth_endpoint.logout(RefreshRequest(refresh_token="refresh-jwt"), db)
    assert result is None
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
