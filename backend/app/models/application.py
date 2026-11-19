# backend/app/models/application.py
from sqlalchemy import Column, String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4
from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False, index=True)           # ex: "IBM DOMINO"
    module = Column(String(100), nullable=True)                      # ex: "Messagerie"
    owner = Column(String(150), nullable=True)                       # ex: "DI"
    direction = Column(String(50), nullable=True)                    # ex: "DI"
    access_level = Column(String(100), nullable=True)                # ex: "Utilisateur / Admin restreint"
    hosting_current = Column(String(100), nullable=True)             # ex: "On-Premise"
    hosting_target = Column(String(100), nullable=True)              # ex: "Cloud IaaS externe"
    criticality = Column(String(20), nullable=False, default="Moyenne")  # Faible/Moyenne/Élevée/Critique
    main_risk = Column(String(200), nullable=True)                   # ex: "Phishing / indisponibilité"
    treatment_plan = Column(Text, nullable=True)                     # ex: "Migration Cloud + PRA"
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Application {self.name} ({self.module}) criticité={self.criticality}>"