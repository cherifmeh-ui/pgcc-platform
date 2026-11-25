import pytest
from uuid import uuid4
from starlette.requests import Request
from fastapi import Response
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints.auth import RefreshRequest


@pytest.mark.asyncio
async def test_logout_invalid_token_is_idempotent(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: (_ for _ in ()).throw(ValueError("invalid")))
    result = await auth_endpoint.logout(
        payload=RefreshRequest(refresh_token="invalid"), request=Request({
            "type": "http", "method": "POST", "path": "/auth/logout", "headers": [],
            "client": ("127.0.0.1", 1234), "server": ("test", 80),
            "scheme": "http", "query_string": b"",
        }), response=Response(), db=db
    )
    assert result is None
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_revokes_refresh_session_by_jti_hash(monkeypatch):
    db = AsyncMock()
    session = MagicMock(id=uuid4(), user_id=uuid4(), revoked_at=None)
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = session
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = "logout@example.test"
    db.execute.side_effect = [session_result, user_result]
    audit = AsyncMock()
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"jti": "logout-jti", "type": expected_type})
    monkeypatch.setattr(auth_endpoint, "enqueue_audit_event", audit)
    request = Request({
        "type": "http", "method": "POST", "path": "/auth/logout",
        "headers": [(b"origin", b"http://localhost:5173"), (b"cookie", b"pgcc_refresh=refresh-jwt")],
        "client": ("127.0.0.1", 1234), "server": ("test", 80),
        "scheme": "http", "query_string": b"",
    })
    response = Response()
    result = await auth_endpoint.logout(
        request=request, response=response, db=db,
        payload=None, refresh_cookie="refresh-jwt",
    )
    assert result is None
    assert session.revoked_at is not None
    assert db.execute.await_count == 2
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "REFRESH_SESSION_LOGOUT"
    db.commit.assert_awaited_once()
    assert "Max-Age=0" in response.headers.get("set-cookie", "")
