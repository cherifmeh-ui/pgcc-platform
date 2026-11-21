# backend/app/models/action_item.py
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Enum as SQLEnum, func, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship  # ⬅️ IMPORT CRUCIAL AJOUTÉ
import enum
from uuid import uuid4
from app.core.database import Base


class ActionStatus(str, enum.Enum):
    TODO = "À faire"
    IN_PROGRESS = "En cours"
    DONE = "Terminé"
    BLOCKED = "Bloqué"


class Priority(str, enum.Enum):
    LOW = "Basse"       # La valeur stockée en DB sera "Basse"
    MEDIUM = "Moyenne"
    HIGH = "Haute"
    CRITICAL = "Critique"


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Optional traceability to an ISO 27002 control assessment
    iso_control_id = Column(Integer, ForeignKey("iso_controls.id", ondelete="RESTRICT"), nullable=True, index=True)
    iso_assessment_id = Column(PG_UUID(as_uuid=True), ForeignKey("iso_control_assessments.id", ondelete="RESTRICT"), nullable=True, index=True)

    # Lien vers le risque parent
    risk_id = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("risks.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    status = Column(SQLEnum(ActionStatus, name='action_status_enum'), default=ActionStatus.TODO)
    priority = Column(SQLEnum(Priority, name='priority_enum'), default=Priority.MEDIUM)
    
    assigned_to = Column(String(100), nullable=True)  # Nom ou email du responsable
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps gérés par SQLAlchemy (pas datetime.utcnow!)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relation inverse vers Risk
    risk = relationship("Risk", back_populates="actions")

    def __repr__(self):
        return f"<ActionItem {self.title} ({self.status})>"