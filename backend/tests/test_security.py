import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-ci-only")

import asyncio
import json

import pytest

from app.core.security import (
    create_access_token,
    create_pre_auth_token,
    create_change_password_token,
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

from pydantic import ValidationError
from app.schemas.risk import RiskCreate, RiskUpdate


def test_risk_schema_accepts_valid_ref_and_status():
    payload = RiskCreate(ref="M-EXT-01", title="Cyber risk", impact=5, likelihood=4, status="En traitement", treatment_plan="Plan de traitement initial.")
    assert payload.ref == "M-EXT-01"
    assert payload.status == "En traitement"


def test_risk_schema_rejects_invalid_ref():
    with pytest.raises(ValidationError):
        RiskCreate(ref="bad ref", title="Cyber risk")


def test_risk_schema_rejects_invalid_status():
    with pytest.raises(ValidationError):
        RiskUpdate(status="Whatever")

from app.services.document_extractor import DocumentExtractor


def test_document_extractor_rejects_unsupported_format():
    with pytest.raises(ValueError, match="non supporté"):
        DocumentExtractor.extract_text(b"malicious", "file.exe")


def test_document_extractor_rejects_invalid_pdf_signature():
    with pytest.raises(ValueError):
        DocumentExtractor.extract_text(b"not a pdf", "file.pdf")


def test_document_extractor_rejects_invalid_docx_archive():
    with pytest.raises(ValueError):
        DocumentExtractor.extract_text(b"PK-not-a-zip", "file.docx")

from app.services.rag_service import _split_text


def test_rag_split_text_empty_and_short_text():
    assert _split_text("", 100, 10) == []
    assert _split_text("one two three", 100, 10) == ["one two three"]


def test_rag_split_text_chunks_and_overlap():
    chunks = _split_text("alpha beta gamma delta epsilon zeta eta theta", 16, 5)
    assert len(chunks) > 1
    assert all(len(chunk) <= 16 for chunk in chunks)
    assert any(set(chunk.split()) & set(chunks[index + 1].split()) for index, chunk in enumerate(chunks[:-1]))


def test_rag_split_text_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        _split_text("text", 0, 0)
    with pytest.raises(ValueError):
        _split_text("text", 10, 10)

from types import SimpleNamespace
from app.services.security_logger import get_client_ip, get_user_agent


def test_security_logger_uses_direct_peer_not_forwarded_header():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.99", "user-agent": "test-agent"},
        client=SimpleNamespace(host="10.0.0.4"),
    )
    assert get_client_ip(request) == "10.0.0.4"


def test_security_logger_truncates_user_agent():
    request = SimpleNamespace(headers={"user-agent": "x" * 400}, client=None)
    assert len(get_user_agent(request)) == 255

def test_risk_schema_requires_treatment_plan_for_accepted_risk():
    with pytest.raises(ValidationError, match="justification"):
        RiskCreate(ref="R-ACCEPT-01", title="Accepted risk", status="Accepté")


def test_risk_schema_accepts_documented_risk_acceptance():
    payload = RiskCreate(
        ref="R-ACCEPT-02",
        title="Accepted risk",
        status="Accepté",
        treatment_plan="Acceptation formelle par la Direction, revue prévue le 31/12.",
    )
    assert payload.status == "Accepté"


def test_risk_schema_requires_plan_for_in_treatment():
    with pytest.raises(ValidationError, match="plan"):
        RiskCreate(ref="R-TREAT-01", title="Treatment risk", status="En traitement")

from scripts.seed_iso_controls import SEED_DATA, validate_seed_data


def test_iso_control_seed_has_93_unique_controls_and_expected_domains():
    validate_seed_data()
    refs = [item[0] for item in SEED_DATA]
    assert len(refs) == 93
    assert len(set(refs)) == 93
    assert sum(ref.startswith("A.5.") for ref in refs) == 37
    assert sum(ref.startswith("A.6.") for ref in refs) == 8
    assert sum(ref.startswith("A.7.") for ref in refs) == 14
    assert sum(ref.startswith("A.8.") for ref in refs) == 34

@pytest.mark.parametrize("reserved_claim", ["sub", "type", "iat", "exp", "jti", "role"])
def test_access_token_rejects_reserved_extra_claim_override(reserved_claim):
    with pytest.raises(ValueError, match="reserved .* claims"):
        create_access_token(
            "user@example.test",
            "viewer",
            extra_claims={reserved_claim: "attacker-controlled"},
        )


def test_access_token_extra_claims_cannot_override_role():
    with pytest.raises(ValueError, match="reserved .* claims"):
        create_access_token(
            "user@example.test",
            "viewer",
            extra_claims={"role": "admin"},
        )

def test_change_password_token_is_typed_and_short_lived():
    token = create_change_password_token("user@example.test", "viewer")
    payload = decode_token(token, expected_type="change_password")
    assert payload["sub"] == "user@example.test"
    assert payload["type"] == "change_password"
    with pytest.raises(Exception):
        decode_token(token, expected_type="access")
