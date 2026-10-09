# backend/app/models/risk.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Risk(Base):
    __tablename__ = "risks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    ref = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    threat = Column(Text, nullable=True)

    impact = Column(Integer, nullable=False, default=3)
    likelihood = Column(Integer, nullable=False, default=3)
    risk_level = Column(Integer, nullable=False, default=9, index=True)

    site = Column(String(100), nullable=True, index=True)

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(String(50), nullable=False, default="Ouvert", index=True)
    treatment_plan = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)