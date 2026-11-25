from unittest.mock import MagicMock

import pytest

from app.api.v1.endpoints.ai_advanced import readable_context_documents


def test_viewer_context_excludes_restricted_documents_before_prompt():
    viewer = MagicMock(role="viewer")
    documents = [
        MagicMock(id="1", doc_type="CONTRAT"),
        MagicMock(id="2", doc_type="PSSI"),
        MagicMock(id="3", doc_type="AUDIT_REPORT"),
        MagicMock(id="4", doc_type="PROCEDURE"),
    ]

    visible = readable_context_documents(viewer, documents)

    assert [document.id for document in visible] == ["2", "4"]


def test_auditor_context_can_include_restricted_documents():
    auditor = MagicMock(role="auditor")
    documents = [
        MagicMock(id="1", doc_type="CONTRAT"),
        MagicMock(id="2", doc_type="AUDIT_REPORT"),
    ]

    visible = readable_context_documents(auditor, documents)

    assert [document.id for document in visible] == ["1", "2"]


def test_context_acl_limits_prompt_sources_to_three_documents():
    viewer = MagicMock(role="viewer")
    documents = [
        MagicMock(id=str(index), doc_type="PSSI")
        for index in range(5)
    ]

    visible = readable_context_documents(viewer, documents)

    assert len(visible) == 3
