# backend/app/models/user.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)

    # Roles backend (minuscules) : admin | executive | auditor | viewer
    role = Column(String(50), nullable=False, default="viewer", index=True)
    password_hash = Column(String(255), nullable=False)

    must_change_password = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # MFA
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    backup_codes_hashed = Column(JSONB, nullable=True)

    # Anti brute-force
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Traçabilité
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_executive(self) -> bool:
        return self.role == "executive"

    @property
    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        return self.locked_until > utcnow()