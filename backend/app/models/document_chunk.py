# backend/app/models/document_chunk.py
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector
import uuid
from app.core.database import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Lien vers le document parent
    document_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Contenu textuel du chunk (fragment)
    content_text = Column(Text, nullable=False)
    
    # Vecteur numérique (dimension 384 pour nomic-embed-text / phi3-mini)
    # Note : La dimension dépend du modèle embedding choisi dans Ollama.
    # Pour 'nomic-embed-text', c'est souvent 768. Pour 'phi3', c'est différent.
    # On va supposer 768 pour commencer (standard Nomic).
    embedding = Column(Vector(768), nullable=True) 
    
    # Métadonnées pour retrouver la source exacte
    page_number = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=True) # Position dans le doc
    
    def __repr__(self):
        return f"<Chunk {self.chunk_index} of Doc {self.document_id}>"