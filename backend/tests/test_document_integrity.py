"""Tests for integrity verification of stored document binaries."""
from types import SimpleNamespace
import hashlib

from app.api.v1.endpoints.documents import document_integrity_valid


def test_document_integrity_accepts_matching_sha256():
    payload = b"%PDF-1.7 test document"
    document = SimpleNamespace(
        file_data=payload,
        file_sha256=hashlib.sha256(payload).hexdigest(),
    )
    assert document_integrity_valid(document) is True


def test_document_integrity_rejects_modified_binary():
    original = b"%PDF-1.7 original"
    document = SimpleNamespace(
        file_data=b"%PDF-1.7 modified",
        file_sha256=hashlib.sha256(original).hexdigest(),
    )
    assert document_integrity_valid(document) is False


def test_document_integrity_fails_closed_for_missing_digest_or_binary():
    assert not document_integrity_valid(
        SimpleNamespace(file_data=b"binary", file_sha256=None)
    )
    assert not document_integrity_valid(
        SimpleNamespace(file_data=None, file_sha256="a" * 64)
    )
    assert not document_integrity_valid(
        SimpleNamespace(file_data=b"", file_sha256="a" * 64)
    )
