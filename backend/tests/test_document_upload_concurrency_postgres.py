"""PostgreSQL test for concurrent duplicate document uploads."""
from __future__ import annotations

import asyncio
import os
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.document import Document
from app.api.v1.endpoints.documents import upload_document

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_concurrent_uploads_with_same_filename_return_one_conflict(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    filename = f"phase0-{uuid4().hex}.pdf"
    prechecks_complete = asyncio.Event()
    precheck_count = 0

    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.DocumentExtractor.extract_text",
        lambda _contents, _filename: ("safe extracted text", "PDF"),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.documents.log_action", AsyncMock()
    )

    async def upload_once():
        nonlocal precheck_count
        async with sessions() as db:
            original_execute = db.execute

            async def synchronized_execute(*args, **kwargs):
                nonlocal precheck_count
                result = await original_execute(*args, **kwargs)
                precheck_count += 1
                if precheck_count == 2:
                    prechecks_complete.set()
                await asyncio.wait_for(prechecks_complete.wait(), timeout=10)
                return result

            db.execute = synchronized_execute
            try:
                await upload_document(
                    request=MagicMock(),
                    file=UploadFile(filename=filename, file=BytesIO(b"%PDF-test")),
                    title="Concurrent upload test",
                    doc_type="PSSI",
                    version=None,
                    author=None,
                    db=db,
                    current_user=MagicMock(email="phase0@example.invalid"),
                )
                return 201
            except HTTPException as exc:
                return exc.status_code

    try:
        results = await asyncio.gather(upload_once(), upload_once())
        assert sorted(results) == [201, 409]

        async with sessions() as verify:
            matching = (await verify.execute(
                select(Document).where(
                    func.lower(func.btrim(Document.filename)) == filename.lower()
                )
            )).scalars().all()
            assert len(matching) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Document).where(
                func.lower(func.btrim(Document.filename)) == filename.lower()
            ))
            await cleanup.commit()
        await engine.dispose()
