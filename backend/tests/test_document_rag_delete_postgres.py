"""PostgreSQL concurrency test for document indexing versus source deletion."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.iso_control_evidence import IsoControlEvidence
from app.services import rag_service
from app.api.v1.endpoints.documents import delete_document

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_rag_indexing_and_document_deletion_are_serialized(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    document_id = uuid4()
    entered_embedding = asyncio.Event()
    release_embedding = asyncio.Event()

    async def controlled_embedding(_texts):
        entered_embedding.set()
        await asyncio.wait_for(release_embedding.wait(), timeout=10)
        return [[0.0] * rag_service.EMBEDDING_DIMENSIONS]

    monkeypatch.setattr(rag_service, "_generate_embeddings", controlled_embedding)

    try:
        async with sessions() as setup:
            document = Document(
                id=document_id,
                title="Phase 0 concurrency test",
                doc_type="PROCEDURE",
                filename=f"phase0-{document_id}.pdf",
                content_text="alpha beta gamma",
                file_data=b"%PDF-test",
                file_size_kb=1,
                mime_type="application/pdf",
                is_indexed=False,
            )
            setup.add(document)
            await setup.commit()

        async def index():
            async with sessions() as db:
                return await rag_service.RAGService.index_document(
                    db, str(document_id), user_email="phase0@example.invalid"
                )

        async def remove():
            async with sessions() as db:
                try:
                    await delete_document(
                        doc_id=str(document_id),
                        request=Request({
                            "type": "http", "method": "DELETE", "path": "/documents/test",
                            "headers": [], "client": ("127.0.0.1", 1234),
                            "server": ("test", 80), "scheme": "http", "query_string": b"",
                        }),
                        db=db,
                        current_user=MagicMock(email="phase0@example.invalid"),
                    )
                    return 204
                except HTTPException as exc:
                    return exc.status_code

        index_task = asyncio.create_task(index())
        await asyncio.wait_for(entered_embedding.wait(), timeout=5)
        delete_task = asyncio.create_task(remove())

        # The delete SELECT must wait for the row lock held by the indexer.
        await asyncio.sleep(0.2)
        assert not delete_task.done(), "document deletion bypassed the indexer's row lock"

        release_embedding.set()
        assert await asyncio.wait_for(index_task, timeout=10) is True
        assert await asyncio.wait_for(delete_task, timeout=10) == 204

        async with sessions() as verify:
            remaining_document = await verify.get(Document, document_id)
            remaining_chunks = (await verify.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )).scalars().all()
            assert remaining_document is None
            assert remaining_chunks == []
    finally:
        release_embedding.set()
        async with sessions() as cleanup:
            await cleanup.execute(delete(IsoControlEvidence).where(
                IsoControlEvidence.document_id == document_id
            ))
            await cleanup.execute(delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            ))
            await cleanup.execute(delete(Document).where(Document.id == document_id))
            await cleanup.commit()
        await engine.dispose()

@pytest.mark.asyncio
async def test_rag_index_rolls_back_chunk_replacement_when_audit_enqueue_fails(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=2, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    document_id = uuid4()
    original_text = "previous indexed content"

    monkeypatch.setattr(
        rag_service, "_generate_embeddings",
        AsyncMock(return_value=[[0.0] * rag_service.EMBEDDING_DIMENSIONS]),
    )
    monkeypatch.setattr(
        rag_service, "enqueue_audit_event",
        AsyncMock(side_effect=RuntimeError("simulated outbox failure")),
    )

    try:
        async with sessions() as setup:
            document = Document(
                id=document_id, title="RAG audit rollback", doc_type="PROCEDURE",
                filename=f"phase0-rag-audit-{document_id}.pdf",
                content_text="new content to index", file_data=b"%PDF-test",
                file_size_kb=1, mime_type="application/pdf", is_indexed=False,
            )
            setup.add(document)
            setup.add(DocumentChunk(
                document_id=document_id, content_text=original_text,
                embedding=[0.0] * rag_service.EMBEDDING_DIMENSIONS, chunk_index=0,
            ))
            await setup.commit()

        async with sessions() as db:
            with pytest.raises(RuntimeError, match="simulated outbox failure"):
                await rag_service.RAGService.index_document(
                    db, str(document_id), user_email="phase0@example.invalid"
                )

        async with sessions() as verify:
            document = await verify.get(Document, document_id)
            chunks = (await verify.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )).scalars().all()
            assert document is not None
            assert document.is_indexed is False
            assert len(chunks) == 1
            assert chunks[0].content_text == original_text
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            ))
            await cleanup.execute(delete(Document).where(Document.id == document_id))
            await cleanup.commit()
        await engine.dispose()
