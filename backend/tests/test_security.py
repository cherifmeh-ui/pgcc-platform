import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-ci-only")

import asyncio
import json

import pytest

from app.core.security import (
    create_access_token,
    create_pre_auth_token,
    decode_token,
    consume_backup_code,
    hash_password,
    verify_password,
)
from app.services.ai_service import AIService


def test_token_types_are_enforced():
    token = create_access_token("user@example.test", "viewer")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user@example.test"
    assert payload["type"] == "access"


def test_pre_auth_token_cannot_be_used_as_access_token():
    token = create_pre_auth_token("user@example.test", "viewer")
    with pytest.raises(Exception):
        decode_token(token, expected_type="access")


def test_password_hash_and_verification():
    hashed = hash_password("Strong-Test-Password-123!")
    assert hashed != "Strong-Test-Password-123!"
    assert verify_password("Strong-Test-Password-123!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_backup_code_is_consumed_once(monkeypatch):
    hashes = ["hash-one", "hash-two"]
    monkeypatch.setattr(
        "app.core.security.verify_password",
        lambda code, hashed: code == "RECOVERY" and hashed == "hash-one",
    )
    remaining = consume_backup_code(" recovery ", hashes)
    assert remaining == ["hash-two"]
    assert consume_backup_code("recovery", remaining) is None


def test_backup_code_invalid_does_not_mutate_list(monkeypatch):
    hashes = ["hash-one", "hash-two"]
    monkeypatch.setattr("app.core.security.verify_password", lambda code, hashed: False)
    assert consume_backup_code("invalid", hashes) is None
    assert hashes == ["hash-one", "hash-two"]


def test_iso_suggestion_parser_filters_invalid_refs(monkeypatch):
    service = AIService()
    response = json.dumps([
        {"ref": "5.7", "title": "Threat intelligence", "rationale": "Relevant; verify implementation."},
        {"ref": "99.99", "title": "Fake control", "rationale": "Invalid reference."},
        {"ref": "6.3", "title": "", "rationale": "Missing title."},
        "malformed item",
    ])
    async def fake_generate_text(prompt, model=None):
        assert "<risk_data>" in prompt
        return response
    monkeypatch.setattr(service, "generate_text", fake_generate_text)
    result = asyncio.run(service.suggest_iso_controls({"title": "Test risk"}))
    assert result == [
        {"ref": "5.7", "title": "Threat intelligence", "rationale": "Relevant; verify implementation."}
    ]


def test_iso_suggestion_parser_rejects_non_json(monkeypatch):
    service = AIService()
    async def fake_generate_text(prompt, model=None):
        return "not json"
    monkeypatch.setattr(service, "generate_text", fake_generate_text)
    with pytest.raises(RuntimeError, match="JSON"):
        asyncio.run(service.suggest_iso_controls({"title": "Test risk"}))
