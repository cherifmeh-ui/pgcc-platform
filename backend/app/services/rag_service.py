# backend/app/services/rag_service.py
import asyncio
import httpx
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.core.config import settings

# Configuration Ollama
OLLAMA_URL = settings.OLLAMA_BASE_URL or "http://host.docker.internal:11434"
EMBED_MODEL = "nomic-embed-text" # Modèle recommandé pour FR/EN mixte
CHUNK_SIZE = 500 # Caractères approximatifs par fragment
CHUNK_OVERLAP = 50 # Chevauchement pour garder le contexte

class RAGService:
    
    @staticmethod
    async def index_document(db: AsyncSession, doc_id: str):
        """Charge un document, le découpe et génère ses embeddings."""
        
        # 1. Récupérer le document
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc or not doc.content_text:
            print(f"⚠️ Document {doc_id} introuvable ou vide.")
            return False
            
        full_text = doc.content_text
        
        # 2. Nettoyer et Découper (Simple Splitting)
        chunks = _split_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
        print(f"📄 Document '{doc.title}' découpé en {len(chunks)} fragments.")
        
        # 3. Supprimer les anciens chunks si ré-indexation
        old_chunks_q = await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        old_chunks = old_chunks_q.scalars().all()
        for oc in old_chunks:
            await db.delete(oc)
            
        # 4. Générer les Embeddings (Batch Processing pour performance)
        # Attention : Ollama peut être lent. On traite par lots de 10.
        BATCH_SIZE = 10
        total_processed = 0
        
        for i in range(0, len(chunks), BATCH_SIZE):
            batch_texts = chunks[i:i+BATCH_SIZE]
            vectors = await _generate_embeddings(batch_texts)
            
            if not vectors:
                print("❌ Échec génération embeddings Ollama.")
                continue
                
            # Sauvegarder chaque chunk avec son vecteur
            for j, vec in enumerate(vectors):
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    content_text=batch_texts[j],
                    embedding=vec, # Le vecteur numpy/list python sera converti par SQLAlchemy
                    chunk_index=i+j,
                    page_number=None # Optionnel
                )
                db.add(chunk_obj)
                
            total_processed += len(batch_texts)
            await db.commit() # Commit après chaque lot pour éviter timeouts longs
            print(f"✅ Lot {i//BATCH_SIZE + 1} traité ({total_processed}/{len(chunks)})")
            
        # Marquer le document comme indexé
        doc.is_indexed = True
        await db.commit()
        
        print(f"🎉 Indexation terminée pour '{doc.title}'.")
        return True

def _split_text(text: str, size: int, overlap: int) -> List[str]:
    """Découpe le texte en chunks avec chevauchement."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_len = 0
    
    for word in words:
        word_len = len(word) + 1 # +1 pour l'espace
        if current_len + word_len > size and current_chunk:
            chunks.append(' '.join(current_chunk))
            # Garder les derniers mots pour le chevauchement
            keep_words = []
            temp_len = 0
            for w in reversed(current_chunk):
                if temp_len + len(w) + 1 <= overlap:
                    keep_words.insert(0, w)
                    temp_len += len(w) + 1
                else:
                    break
            current_chunk = keep_words
            current_len = temp_len
        
        current_chunk.append(word)
        current_len += word_len
        
    if current_chunk:
        chunks.append(' '.join(current_chunk))
        
    return chunks

async def _generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Appelle Ollama pour obtenir les vecteurs."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": EMBED_MODEL,
                "prompt": texts, # Ollama accepte une liste de prompts pour batching
                "keep_alive": "5m"
            }
            resp = await client.post(f"{OLLAMA_URL}/api/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Format réponse Ollama embeddings : {"embeddings": [[...], [...]]}
            if "embeddings" in data:
                return data["embeddings"]
            else:
                print(f"⚠️ Format réponse Ollama inattendu : {list(data.keys())}")
                return []
                
    except Exception as e:
        print(f"💥 Erreur appel Ollama Embeddings : {e}")
        return []

# Instance globale
rag_service = RAGService()