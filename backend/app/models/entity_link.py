# backend/app/models/entity_link.py
from sqlalchemy import Column, String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import enum
from uuid import uuid4
from app.core.database import Base


class EntityType(str, enum.Enum):
    RISK = "risk"
    APPLICATION = "application"
    SERVER = "server"
    CONTROL_ISO = "iso_control"
    DOCUMENT = "document"


class LinkType(str, enum.Enum):
    MITIGATES = "mitigates"      # Un contrôle/mitigation réduit un risque
    HOSTS = "hosts"              # Une app héberge un service/donnée
    REFERENCES = "references"     # Un document cite un risque/contrôle
    IMPACTS = "impacts"          # Un incident impacte une app


class EntityLink(Base):
    __tablename__ = "entity_links"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    source_id = Column(PG_UUID(as_uuid=True), nullable=False)
    source_type = Column(SQLEnum(EntityType), nullable=False)
    
    target_id = Column(PG_UUID(as_uuid=True), nullable=False)
    target_type = Column(SQLEnum(EntityType), nullable=False)
    
    link_type = Column(SQLEnum(LinkType), nullable=False)
    
    # ✅ CORRECTION ICI : Integer est maintenant importé
    confidence_score = Column(Integer, default=100) 
    
    description = Column(String(500), nullable=True) 

    def __repr__(self):
        return f"<Link {self.source_type}:{self.source_id} -> {self.target_type}:{self.target_id}>"