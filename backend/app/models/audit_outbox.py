"""Durable queue for security audit events awaiting log delivery."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AuditOutbox(Base):
    __tablename__ = "audit_outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_audit_outbox_pending",
            created_at,
            postgresql_where=text("delivered_at IS NULL"),
        ),
    )
