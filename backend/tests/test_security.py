import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-ci-only")

from app.core.security import create_access_token, create_pre_auth_token, decode_token, consume_backup_code


def test_token_types_are_enforced():
    token = create_access_token("user@example.test", "viewer")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user@example.test"
    assert payload["type"] == "access"


def test_pre_auth_token_cannot_be_used_as_access_token():
    token = create_pre_auth_token("user@example.test", "viewer")
    try:
        decode_token(token, expected_type="access")
    except Exception:
        pass
    else:
        raise AssertionError("Pre-auth token accepted as access token")


def test_backup_code_is_consumed_once(monkeypatch):
    hashes = ["hash-one", "hash-two"]
    monkeypatch.setattr("app.core.security.verify_password", lambda code, hashed: code == "RECOVERY" and hashed == "hash-one")
    remaining = consume_backup_code(" recovery ", hashes)
    assert remaining == ["hash-two"]
    assert consume_backup_code("recovery", remaining) is None
