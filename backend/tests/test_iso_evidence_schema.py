from pydantic import ValidationError
import pytest

from app.api.v1.endpoints.compliance import EvidenceCreate, EvidenceVerify


def test_evidence_create_accepts_optional_metadata():
    payload = EvidenceCreate(document_id="12345678-1234-5678-1234-567812345678")
    assert payload.evidence_owner is None
    assert payload.notes is None


def test_evidence_create_rejects_invalid_date_range():
    with pytest.raises(ValidationError):
        EvidenceCreate(
            document_id="12345678-1234-5678-1234-567812345678",
            collected_at="2026-11-20T00:00:00Z",
            valid_until="2026-11-19T00:00:00Z",
        )


@pytest.mark.parametrize("status", ["Verified", "Rejected", "Pending"])
def test_evidence_verify_accepts_supported_status(status):
    assert EvidenceVerify(verification_status=status).verification_status == status


def test_evidence_verify_rejects_unknown_status():
    with pytest.raises(ValidationError):
        EvidenceVerify(verification_status="Approved")
