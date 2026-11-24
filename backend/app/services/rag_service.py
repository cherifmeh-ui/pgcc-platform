# backend/app/services/rag_service.py
import httpx
from typing import List, Optional
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.core.config import settings
from app.services.security_logger import enqueue_audit_event

OLLAMA_URL = (settings.OLLAMA_BASE_URL or "http://host.docker.internal:11434").rstrip("/")
EMBED_MODEL = "nomic-embed-text"
EMBEDDING_DIMENSIONS = 768
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
BATCH_SIZE = 10
MAX_CHUNKS_PER_DOCUMENT = 2000


class RAGService:
    @staticmethod
    async def index_document(
        db: AsyncSession, doc_id: str, *, user_email: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> bool:
        """Generate all vectors first, then atomically replace a document's chunks."""
        result = await db.execute(select(Document).where(Document.id == doc_id).with_for_update())
        doc = result.scalar_one_or_none()
        if not doc or not doc.content_text or not doc.content_text.strip():
            return False

        chunks = _split_text(doc.content_text, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunks:
            return False
        if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
            raise RuntimeError(
                f"Document trop volumineux pour l'indexation ({len(chunks)} chunks; "
                f"limite {MAX_CHUNKS_PER_DOCUMENT})."
            )

        vectors: List[List[float]] = []
        try:
            for start in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[start:start + BATCH_SIZE]
                batch_vectors = await _generate_embeddings(batch)
                if len(batch_vectors) != len(batch):
                    raise RuntimeError("Ollama a retourné un nombre d'embeddings inattendu.")
                for vector in batch_vectors:
                    if len(vector) != EMBEDDING_DIMENSIONS:
                        raise RuntimeError(
                            f"Dimension embedding invalide: {len(vector)}; "
                            f"attendu {EMBEDDING_DIMENSIONS}."
                        )
                vectors.extend(batch_vectors)

            if len(vectors) != len(chunks):
                raise RuntimeError("Indexation incomplète: certains chunks n'ont pas de vecteur.")

            old_result = await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )
            for old_chunk in old_result.scalars().all():
                await db.delete(old_chunk)

            for index, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                db.add(DocumentChunk(
                    document_id=doc.id,
                    content_text=chunk_text,
                    embedding=vector,
                    chunk_index=index,
                    page_number=None,
                ))

            doc.is_indexed = True
            if user_email:
                await enqueue_audit_event(
                    db, user_email=user_email, action="INDEX", resource="documents",
                    resource_id=str(doc.id), details=f"Document indexed: {doc.title}",
                    event_type="DOCUMENT", request=request,
                )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            # Preserve existing chunks if generation or persistence failed.
            raise


def _split_text(text: str, size: int, overlap: int) -> List[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Paramètres de découpage invalides.")
    words = text.split()
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + (1 if current else 0)
        if current and current_len + word_len > size:
            chunks.append(" ".join(current))
            keep: List[str] = []
            keep_len = 0
            for item in reversed(current):
                item_len = len(item) + (1 if keep else 0)
                if keep_len + item_len > overlap:
                    break
                keep.insert(0, item)
                keep_len += item_len
            current = keep
            current_len = keep_len

        # Avoid a single very long token creating an oversized chunk.
        if len(word) > size:
            if current:
                chunks.append(" ".join(current))
                current, current_len = [], 0
            for start in range(0, len(word), size):
                chunks.append(word[start:start + size])
            continue

        word_len = len(word) + (1 if current else 0)
        current.append(word)
        current_len += word_len

    if current:
        chunks.append(" ".join(current))
    return chunks


async def _generate_embeddings(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    try:
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": texts, "keep_alive": "5m"},
            )
            response.raise_for_status()
            data = response.json()
            vectors = data.get("embeddings")
            if not isinstance(vectors, list):
                raise RuntimeError("Réponse Ollama embeddings invalide.")
            if any(not isinstance(vector, list) for vector in vectors):
                raise RuntimeError("Format de vecteur Ollama invalide.")
            return vectors
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Échec de génération des embeddings Ollama.") from exc


rag_service = RAGService()
