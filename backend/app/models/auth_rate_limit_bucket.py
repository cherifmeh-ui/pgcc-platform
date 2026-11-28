"""Shared PostgreSQL-backed authentication rate-limit buckets."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, func

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthRateLimitBucket(Base):
    __tablename__ = "auth_rate_limit_buckets"

    bucket_key = Column(String(64), primary_key=True)
    scope = Column(String(32), nullable=False)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_auth_rate_limit_buckets_attempts_nonnegative"),
        Index("ix_auth_rate_limit_buckets_updated_at", "updated_at"),
    )
