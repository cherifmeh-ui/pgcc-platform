# backend/app/models/iso_control.py
from sqlalchemy import Column, String, Text, Integer, Boolean
from app.core.database import Base

class IsoControl(Base):
    __tablename__ = "iso_controls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Référence officielle ISO (ex: "A.5.1", "A.8.9")
    ref_code = Column(String(20), unique=True, nullable=False, index=True)
    
    # Titre du contrôle
    title = Column(String(200), nullable=False)
    
    # Description détaillée / Exigence normative
    description = Column(Text, nullable=True)
    
    # Domaine thématique (ex: "Organisation", "Technique", "Personnel")
    domain = Column(String(50), nullable=False)
    
    # Catégorie ISO (ex: "Contexte", "Sécurité Physique")
    category = Column(String(100), nullable=True)
    
    # Statut manuel override (si le RSSI décide qu'il est couvert malgré absence de lien technique)
    is_manually_covered = Column(Boolean, default=False)

    def __repr__(self):
        return f"<IsoControl {self.ref_code}: {self.title}>"