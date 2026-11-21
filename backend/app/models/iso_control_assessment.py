"""Persisted ISO control assessments for auditable compliance evaluation."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class IsoControlAssessment(Base):
    __tablename__ = "iso_control_assessments"
    __table_args__ = (
        CheckConstraint("applicability IN (\'Applicable\', \'Non applicable\')", name="ck_iso_assessment_applicability"),
        CheckConstraint("implementation_status IN (\'Non démarré\', \'En cours\', \'Implémenté\', \'Partiellement implémenté\')", name="ck_iso_assessment_status"),
        CheckConstraint("maturity_level >= 0 AND maturity_level <= 5", name="ck_iso_assessment_maturity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    control_id = Column(Integer, ForeignKey("iso_controls.id", ondelete="RESTRICT"), nullable=False, index=True)
    assessed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    applicability = Column(String(20), nullable=False)
    implementation_status = Column(String(30), nullable=False)
    maturity_level = Column(Integer, nullable=False)
    justification = Column(Text, nullable=False)
    gap_description = Column(Text, nullable=True)
    assessed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
