# backend/app/models/document.py
from sqlalchemy import Column, String, Integer, DateTime, LargeBinary, Text, Boolean, Index, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime
from uuid import uuid4
from app.core.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    title = Column(String(200), nullable=False)
    doc_type = Column(String(50), nullable=False) # ex: "PSSI", "Procedure", "Contrat"
    version = Column(String(20), nullable=True)
    author = Column(String(100), nullable=True)
    
    # Contenu extrait (Texte pur pour recherche IA)
    content_text = Column(Text, nullable=True) 
    
    # Fichier original (Binaire) - Optionnel selon stratégie stockage
    file_data = Column(LargeBinary, nullable=True) 
    filename = Column(String(200), nullable=True)

    __table_args__ = (
        Index(
            "uq_documents_filename_ci",
            func.lower(func.btrim(filename)),
            unique=True,
            postgresql_where=text("filename IS NOT NULL AND btrim(filename) <> ''"),
        ),
    )
    
    # Métadonnées techniques
    file_size_kb = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    is_indexed = Column(Boolean, default=False) # Flag pour savoir si prêt pour Vectorisation
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Document {self.title} ({self.doc_type})>"