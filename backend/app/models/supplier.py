"""Third-party supplier register models (TPRM)."""
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "criticality IN ('Faible', 'Moyenne', 'Élevée', 'Critique')",
            name="ck_suppliers_criticality",
        ),
        CheckConstraint(
            "dependency_level IN ('Faible', 'Moyenne', 'Élevée', 'Critique')",
            name="ck_suppliers_dependency_level",
        ),
        CheckConstraint(
            "status IN ('À qualifier', 'En évaluation', 'Approuvé', "
            "'Approuvé sous conditions', 'Suspendu', 'Terminé')",
            name="ck_suppliers_status",
        ),
        UniqueConstraint("code", name="uq_suppliers_code"),
        Index("uq_suppliers_code_ci", text("lower(code)"), unique=True),
        Index("ix_suppliers_active_criticality", "archived_at", "criticality"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    code = Column(String(40), nullable=False, index=True)
    legal_name = Column(String(200), nullable=False, index=True)
    trade_name = Column(String(200), nullable=True)
    country = Column(String(100), nullable=True)
    service_category = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    business_owner_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    direction = Column(String(100), nullable=True, index=True)
    criticality = Column(String(20), nullable=False, default="Moyenne", index=True)
    dependency_level = Column(String(20), nullable=False, default="Moyenne")
    data_categories = Column(Text, nullable=True)
    hosting_location = Column(String(200), nullable=True)
    uses_subprocessors = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(String(40), nullable=False, default="À qualifier", index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierContact(Base):
    __tablename__ = "supplier_contacts"
    __table_args__ = (
        CheckConstraint(
            "contact_type IN ('Commercial', 'Technique', 'Sécurité', 'Contractuel', 'Autre')",
            name="ck_supplier_contacts_type",
        ),
        Index("ix_supplier_contacts_supplier_active", "supplier_id", "is_active"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    full_name = Column(String(150), nullable=False)
    role = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    contact_type = Column(String(20), nullable=False, default="Autre")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
