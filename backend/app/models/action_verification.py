"""Post-action effectiveness verification records."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ActionVerification(Base):
    __tablename__ = "action_verifications"
    __table_args__ = (
        CheckConstraint("outcome IN ('Effective', 'Ineffective', 'Follow-up required')", name="ck_action_verification_outcome"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_id = Column(UUID(as_uuid=True), ForeignKey("action_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    verified_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True, index=True)
    outcome = Column(Text, nullable=False)
    notes = Column(Text, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
