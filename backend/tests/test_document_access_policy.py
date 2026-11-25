from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api.v1.endpoints.documents import (
    INTERNAL_DOCUMENT_TYPES,
    can_read_document,
    document_classification,
    download_document,
    list_documents,
    preview_document,
)


@pytest.mark.parametrize(
    ("doc_type", "classification"),
    [
        ("PSSI", "INTERNAL"),
        ("procedure", "INTERNAL"),
        ("REGLEMENT_INTERIEUR", "INTERNAL"),
        ("CONTRAT", "RESTRICTED"),
        ("AUDIT_REPORT", "RESTRICTED"),
        ("UNKNOWN_LEGACY_TYPE", "RESTRICTED"),
        ("", "RESTRICTED"),
        (None, "RESTRICTED"),
    ],
)
def test_document_classification_fails_closed(doc_type, classification):
    assert document_classification(doc_type) == classification


@pytest.mark.parametrize("doc_type", ["PSSI", "PROCEDURE", "REGLEMENT_INTERIEUR"])
def test_viewer_can_read_only_internal_document_types(doc_type):
    user = MagicMock(role="viewer")
    document = MagicMock(doc_type=doc_type)
    assert can_read_document(user, document) is True


@pytest.mark.parametrize("doc_type", ["CONTRAT", "AUDIT_REPORT", "UNCLASSIFIED"])
def test_viewer_cannot_read_restricted_or_unknown_document_types(doc_type):
    user = MagicMock(role="viewer")
    document = MagicMock(doc_type=doc_type)
    assert can_read_document(user, document) is False


@pytest.mark.parametrize("role", ["admin", "executive", "auditor"])
@pytest.mark.parametrize("doc_type", ["PSSI", "CONTRAT", "AUDIT_REPORT", "UNKNOWN"])
def test_privileged_document_roles_can_read_all_classifications(role, doc_type):
    assert can_read_document(MagicMock(role=role), MagicMock(doc_type=doc_type)) is True


@pytest.mark.asyncio
async def test_viewer_document_list_query_filters_to_internal_types():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        MagicMock(
            id=uuid4(), title="PSSI", doc_type="PSSI", filename="pssi.pdf",
            version="1", author="RSSI", file_size_kb=10, is_indexed=False,
            created_at=None,
        )
    ]
    db.execute.return_value = result

    rows = await list_documents(db=db, current_user=MagicMock(role="viewer"))

    query = db.execute.await_args.args[0]
    compiled = query.compile(dialect=postgresql.dialect())
    assert "upper(documents.doc_type) IN" in str(compiled)
    assert any(
        isinstance(value, tuple) and set(value) == set(INTERNAL_DOCUMENT_TYPES)
        for value in compiled.params.values()
    )
    assert rows[0]["classification"] == "INTERNAL"


@pytest.mark.asyncio
async def test_viewer_direct_download_of_restricted_document_is_hidden():
    doc = MagicMock(id=uuid4(), doc_type="CONTRAT", file_data=b"secret contract")
    result = MagicMock()
    result.scalar_one_or_none.return_value = doc
    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await download_document(
            str(doc.id), db=db, current_user=MagicMock(role="viewer")
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_viewer_direct_preview_of_restricted_document_is_hidden():
    doc = MagicMock(id=uuid4(), doc_type="AUDIT_REPORT", content_text="confidential audit")
    result = MagicMock()
    result.scalar_one_or_none.return_value = doc
    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await preview_document(
            str(doc.id), db=db, current_user=MagicMock(role="viewer")
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_viewer_can_preview_internal_policy_document():
    doc = MagicMock(
        id=uuid4(), doc_type="PSSI", content_text="internal policy",
        title="PSSI", filename="pssi.pdf", version="1", author="RSSI",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = doc
    db = AsyncMock()
    db.execute.return_value = result

    response = await preview_document(
        str(doc.id), db=db, current_user=MagicMock(role="viewer")
    )
    assert response["classification"] == "INTERNAL"
    assert response["preview"] == "internal policy"
