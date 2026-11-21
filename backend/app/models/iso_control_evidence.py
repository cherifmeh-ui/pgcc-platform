"""Evidence records linking source documents to ISO controls and assessments."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class IsoControlEvidence(Base):
    __tablename__ = "iso_control_evidence"
    __table_args__ = (
        CheckConstraint("verification_status IN ('Pending', 'Verified', 'Rejected')", name="ck_iso_evidence_verification_status"),
        UniqueConstraint("document_id", "control_id", name="uq_iso_evidence_document_control"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    control_id = Column(Integer, ForeignKey("iso_controls.id", ondelete="RESTRICT"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("iso_control_assessments.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence_owner = Column(String(150), nullable=True)
    collected_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(String(20), nullable=False, default="Pending")
    verified_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    sha256 = Column(String(64), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
