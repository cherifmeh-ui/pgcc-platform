# backend/app/models/security_log.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SecurityLog(Base):
    __tablename__ = "security_logs"
    # PostgreSQL migration 0023 enforces append-only semantics for UPDATE/DELETE/TRUNCATE.

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)

    event_type = Column(String(50), nullable=False, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)