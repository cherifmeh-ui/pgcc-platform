"""PostgreSQL integration tests for document classification and row-level access."""
from __future__ import annotations

import os
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.documents import (
    download_document,
    list_documents,
    preview_document,
)
from app.models.document import Document

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_postgres_document_list_preview_and_download_enforce_classification():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    marker = uuid4().hex
    docs = [
        Document(
            title=f"Internal policy {marker}", doc_type="PSSI",
            filename=f"phase0-{marker}-policy.pdf", content_text="employee policy",
            file_data=b"%PDF-policy", file_size_kb=1, mime_type="application/pdf",
            is_indexed=False,
        ),
        Document(
            title=f"Restricted contract {marker}", doc_type="CONTRAT",
            filename=f"phase0-{marker}-contract.pdf", content_text="supplier contract secret",
            file_data=b"%PDF-contract", file_size_kb=1, mime_type="application/pdf",
            is_indexed=False,
        ),
        Document(
            title=f"Unknown legacy {marker}", doc_type="LEGACY_UNKNOWN",
            filename=f"phase0-{marker}-unknown.pdf", content_text="legacy restricted content",
            file_data=b"%PDF-unknown", file_size_kb=1, mime_type="application/pdf",
            is_indexed=False,
        ),
    ]
    try:
        async with sessions() as setup:
            setup.add_all(docs)
            await setup.commit()
            for doc in docs:
                await setup.refresh(doc)

        viewer = MagicMock(role="viewer")
        admin = MagicMock(role="admin")
        async with sessions() as db:
            viewer_rows = await list_documents(db=db, current_user=viewer)
            admin_rows = await list_documents(db=db, current_user=admin)
            viewer_filenames = {row["filename"] for row in viewer_rows}
            admin_filenames = {row["filename"] for row in admin_rows}
            assert docs[0].filename in viewer_filenames
            assert docs[1].filename not in viewer_filenames
            assert docs[2].filename not in viewer_filenames
            assert all(doc.filename in admin_filenames for doc in docs)

            with pytest.raises(HTTPException) as preview_denied:
                await preview_document(str(docs[1].id), db=db, current_user=viewer)
            assert preview_denied.value.status_code == 404

            with pytest.raises(HTTPException) as download_denied:
                await download_document(str(docs[1].id), db=db, current_user=viewer)
            assert download_denied.value.status_code == 404

            preview = await preview_document(str(docs[0].id), db=db, current_user=viewer)
            assert preview["classification"] == "INTERNAL"
            assert preview["preview"] == "employee policy"

            download = await download_document(str(docs[0].id), db=db, current_user=viewer)
            assert download.body == b"%PDF-policy"
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(Document).where(Document.filename.like(f"phase0-{marker}-%"))
            )
            await cleanup.commit()
        await engine.dispose()
