from unittest.mock import MagicMock
import hashlib

import pytest

from app.api.v1.endpoints.ai_advanced import readable_context_documents, readable_context_scope


def _document(doc_id, doc_type, payload=None, digest=None):
    payload = payload if payload is not None else ("document-" + doc_id).encode()
    return MagicMock(
        id=doc_id, doc_type=doc_type, file_data=payload,
        file_sha256=digest or hashlib.sha256(payload).hexdigest(),
    )


def test_viewer_context_excludes_restricted_documents_before_prompt():
    viewer = MagicMock(role="viewer")
    documents = [
        _document("1", "CONTRAT"),
        _document("2", "PSSI"),
        _document("3", "AUDIT_REPORT"),
        _document("4", "PROCEDURE"),
    ]

    visible = readable_context_documents(viewer, documents)

    assert [document.id for document in visible] == ["2", "4"]


def test_auditor_context_can_include_restricted_documents():
    auditor = MagicMock(role="auditor")
    documents = [
        _document("1", "CONTRAT"),
        _document("2", "AUDIT_REPORT"),
    ]

    visible = readable_context_documents(auditor, documents)

    assert [document.id for document in visible] == ["1", "2"]


def test_context_acl_limits_prompt_sources_to_three_documents():
    viewer = MagicMock(role="viewer")
    documents = [
        _document(str(index), "PSSI")
        for index in range(5)
    ]

    visible = readable_context_documents(viewer, documents)

    assert len(visible) == 3



def test_context_excludes_document_with_modified_binary():
    viewer = MagicMock(role="viewer")
    original = b"%PDF-1.7 original"
    corrupted = _document(
        "corrupted", "PSSI", payload=b"%PDF-1.7 modified",
        digest=hashlib.sha256(original).hexdigest(),
    )
    valid = _document("valid", "PSSI")
    visible = readable_context_documents(viewer, [corrupted, valid])
    assert [document.id for document in visible] == ["valid"]


def test_context_excludes_document_without_binary_digest():
    viewer = MagicMock(role="viewer")
    missing_digest = MagicMock(
        id="legacy", doc_type="PSSI", file_data=b"legacy content", file_sha256=None
    )
    assert readable_context_documents(viewer, [missing_digest]) == []



def test_viewer_document_scope_is_pushed_into_sql():
    viewer = MagicMock(role="viewer", id=None, department=" DI ")
    compiled = str(readable_context_scope(viewer).compile())
    assert "documents.owner_id IS NULL" in compiled
    assert "documents.department IS NULL" in compiled
    assert "documents.doc_type" in compiled
    assert "documents.department" in compiled


def test_privileged_document_scope_does_not_add_restrictive_filter():
    assert readable_context_scope(MagicMock(role=" AUDITOR ")) is None


def test_unprivileged_non_viewer_document_scope_fails_closed():
    compiled = str(readable_context_scope(MagicMock(role="editor")).compile())
    assert "false" in compiled.lower()
