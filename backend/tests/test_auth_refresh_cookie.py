import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.api.v1.endpoints.auth import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    TokenPairResponse,
    refresh_tokens,
    _clear_refresh_cookie,
    _require_trusted_cookie_origin,
    _set_refresh_cookie,
)
from app.core.config import settings


def test_refresh_cookie_is_http_only_secure_and_path_scoped(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()
    _set_refresh_cookie(response, "test-refresh-token")
    header = response.headers.get("set-cookie")
    assert f"{REFRESH_COOKIE_NAME}=test-refresh-token" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=strict" in header
    assert f"Path={REFRESH_COOKIE_PATH}" in header


def test_refresh_cookie_is_cleared_with_matching_path(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()
    _clear_refresh_cookie(response)
    header = response.headers.get("set-cookie")
    assert f"{REFRESH_COOKIE_NAME}=" in header
    assert "Max-Age=0" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=strict" in header
    assert f"Path={REFRESH_COOKIE_PATH}" in header


def test_token_pair_response_never_exposes_refresh_token():
    assert "refresh_token" not in TokenPairResponse.model_fields


def test_cookie_origin_must_match_explicit_cors_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://pgcc.example,https://admin.pgcc.example")
    request = Request({
        "type": "http", "method": "POST", "path": "/api/v1/auth/refresh",
        "headers": [(b"origin", b"https://pgcc.example")],
        "client": ("127.0.0.1", 1234), "server": ("pgcc.example", 443),
        "scheme": "https", "query_string": b"",
    })
    _require_trusted_cookie_origin(request)


def test_cookie_origin_rejects_missing_or_untrusted_origin(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://pgcc.example")
    for headers in ([], [(b"origin", b"https://evil.example")]):
        request = Request({
            "type": "http", "method": "POST", "path": "/api/v1/auth/refresh",
            "headers": headers, "client": ("127.0.0.1", 1234),
            "server": ("pgcc.example", 443), "scheme": "https",
            "query_string": b"",
        })
        with pytest.raises(HTTPException) as exc:
            _require_trusted_cookie_origin(request)
        assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_refresh_rejects_untrusted_origin_before_database_access(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://pgcc.example")
    request = Request({
        "type": "http", "method": "POST", "path": "/api/v1/auth/refresh",
        "headers": [(b"origin", b"https://attacker.example")],
        "client": ("127.0.0.1", 1234), "server": ("pgcc.example", 443),
        "scheme": "https", "query_string": b"",
    })
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await refresh_tokens(
            request=request, response=Response(), db=db,
            payload=None, refresh_cookie="cookie-token",
        )
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()
