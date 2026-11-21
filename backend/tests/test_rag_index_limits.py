from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import rag_service


@pytest.mark.asyncio
async def test_index_document_rejects_chunk_count_over_limit(monkeypatch):
    document = MagicMock()
    document.content_text = "text"
    document.is_indexed = False
    result = MagicMock()
    result.scalar_one_or_none.return_value = document

    db = AsyncMock()
    db.execute.return_value = result

    monkeypatch.setattr(
        rag_service,
        "_split_text",
        lambda text, size, overlap: ["chunk"] * (rag_service.MAX_CHUNKS_PER_DOCUMENT + 1),
    )
    monkeypatch.setattr(rag_service, "_generate_embeddings", AsyncMock())

    with pytest.raises(RuntimeError, match="Document trop volumineux"):
        await rag_service.RAGService.index_document(db, "document-id")

    db.commit.assert_not_awaited()
    rag_service._generate_embeddings.assert_not_awaited()
