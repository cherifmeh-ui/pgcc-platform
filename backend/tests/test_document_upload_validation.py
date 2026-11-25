"""Validation tests for untrusted document uploads."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.endpoints.documents import upload_document


def _upload(filename: str, payload: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(payload))


async def _call_upload(filename: str, payload: bytes):
    return await upload_document(
        request=MagicMock(),
        file=_upload(filename, payload),
        title="Document de test",
        doc_type="PSSI",
        version=None,
        author=None,
        db=AsyncMock(),
        current_user=MagicMock(email="upload-test@example.invalid"),
    )


@pytest.mark.asyncio
async def test_upload_rejects_payload_over_ten_megabytes():
    with pytest.raises(HTTPException) as error:
        await _call_upload("oversized.pdf", b"A" * (10 * 1024 * 1024 + 1))
    assert error.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension_before_database_access():
    db = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await upload_document(
            request=MagicMock(),
            file=_upload("payload.exe", b"MZ" + b"\x00" * 16),
            title="Document de test",
            doc_type="PSSI",
            version=None,
            author=None,
            db=db,
            current_user=MagicMock(email="upload-test@example.invalid"),
        )
    assert error.value.status_code == 400
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_pdf_extension_with_non_pdf_signature():
    db = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await upload_document(
            request=MagicMock(),
            file=_upload("fake.pdf", b"not a PDF document"),
            title="Document de test",
            doc_type="PSSI",
            version=None,
            author=None,
            db=db,
            current_user=MagicMock(email="upload-test@example.invalid"),
        )
    assert error.value.status_code == 400
    assert "Signature PDF invalide" in error.value.detail
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_docx_with_zip_magic_but_invalid_archive(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.documents.scan_document_bytes", AsyncMock())
    with pytest.raises(HTTPException) as error:
        await upload_document(
            request=MagicMock(),
            file=_upload("fake.docx", b"PK-not-a-valid-zip-archive"),
            title="Document de test",
            doc_type="PSSI",
            version=None,
            author=None,
            db=db,
            current_user=MagicMock(email="upload-test@example.invalid"),
        )
    assert error.value.status_code == 400
    assert "Échec de l'extraction" in error.value.detail
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_empty_file():
    db = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await upload_document(
            request=MagicMock(),
            file=_upload("empty.pdf", b""),
            title="Document de test",
            doc_type="PSSI",
            version=None,
            author=None,
            db=db,
            current_user=MagicMock(email="upload-test@example.invalid"),
        )
    assert error.value.status_code == 400
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_fails_closed_when_antivirus_is_unavailable(monkeypatch):
    from app.services.antivirus import AntivirusUnavailable

    db = AsyncMock()
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.scan_document_bytes",
        AsyncMock(side_effect=AntivirusUnavailable("scanner offline")),
    )
    with pytest.raises(HTTPException) as error:
        await upload_document(
            request=MagicMock(),
            file=_upload("valid.pdf", b"%PDF-valid"),
            title="Document de test",
            doc_type="PSSI",
            version=None,
            author=None,
            db=db,
            current_user=MagicMock(email="upload-test@example.invalid"),
        )
    assert error.value.status_code == 503
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_malware_before_extraction_or_database(monkeypatch):
    from app.services.antivirus import MalwareDetected

    db = AsyncMock()
    extractor = MagicMock()
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.scan_document_bytes",
        AsyncMock(side_effect=MalwareDetected("Eicar")),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.DocumentExtractor.extract_text",
        extractor,
    )
    with pytest.raises(HTTPException) as error:
        await upload_document(
            request=MagicMock(),
            file=_upload("infected.pdf", b"%PDF-malware"),
            title="Document de test",
            doc_type="PSSI",
            version=None,
            author=None,
            db=db,
            current_user=MagicMock(email="upload-test@example.invalid"),
        )
    assert error.value.status_code == 422
    extractor.assert_not_called()
    db.execute.assert_not_awaited()
