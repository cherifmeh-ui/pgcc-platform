from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints import auth as auth_endpoint


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, record):
        self.added.append(record)


@pytest.mark.parametrize("jti", ["token-id-1", "another-token-id"])
def test_refresh_jti_hash_is_sha256_and_stable(jti):
    import hashlib

    token_data = {"jti": jti}
    expected = hashlib.sha256(jti.encode("utf-8")).hexdigest()
    assert auth_endpoint._refresh_jti_hash(token_data) == expected
    assert auth_endpoint._refresh_jti_hash(token_data) == expected
    assert len(expected) == 64


def test_refresh_jti_hash_rejects_missing_or_invalid_jti():
    from fastapi import HTTPException

    for payload in ({}, {"jti": ""}, {"jti": 123}):
        with pytest.raises(HTTPException) as exc:
            auth_endpoint._refresh_jti_hash(payload)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_persist_refresh_session_stores_hash_and_expiry_not_raw_token(monkeypatch):
    user_id = uuid4()
    expires_epoch = 1_800_000_000
    jti = "raw-jti-value"
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: {"jti": jti, "exp": expires_epoch, "type": expected_type})
    db = FakeDB()
    user = SimpleNamespace(id=user_id)
    raw_token = "jwt-secret-token-value"

    token_hash = await auth_endpoint._persist_refresh_session(db, user, raw_token)

    assert len(db.added) == 1
    record = db.added[0]
    assert record.user_id == user_id
    assert record.token_jti_hash == token_hash
    assert record.expires_at == datetime.fromtimestamp(expires_epoch, tz=timezone.utc)
    assert raw_token not in repr(record)
    assert record.revoked_at is None


@pytest.mark.asyncio
async def test_persist_refresh_session_requires_refresh_token_type(monkeypatch):
    db = FakeDB()
    user = SimpleNamespace(id=uuid4())
    calls = []
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type: calls.append(expected_type) or {"jti": "id", "exp": 1})
    await auth_endpoint._persist_refresh_session(db, user, "token")
    assert calls == ["refresh"]
    assert len(db.added) == 1
