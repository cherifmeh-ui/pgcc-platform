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

class SupplierContract(Base):
    """Contractual relationship with a supplier; files remain in Documents."""
    __tablename__ = "supplier_contracts"
    __table_args__ = (
        CheckConstraint("contract_type IN ('Service', 'Maintenance', 'Hébergement', 'Infogérance', 'Licence', 'Autre')", name="ck_supplier_contracts_type"),
        CheckConstraint("status IN ('Brouillon', 'En validation', 'Actif', 'À renouveler', 'Expiré', 'Résilié')", name="ck_supplier_contracts_status"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_supplier_contracts_dates"),
        CheckConstraint("notice_period_days >= 0 AND notice_period_days <= 3650", name="ck_supplier_contracts_notice"),
        UniqueConstraint("supplier_id", "reference", name="uq_supplier_contracts_supplier_reference"),
        Index("uq_supplier_contract_reference_ci", "supplier_id", text("lower(reference)"), unique=True),
        Index("ix_supplier_contracts_supplier_status_end", "supplier_id", "status", "end_date"),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    reference = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    contract_type = Column(String(30), nullable=False, default="Service")
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    notice_period_days = Column(Integer, nullable=False, default=90, server_default="90")
    auto_renew = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(String(30), nullable=False, default="Brouillon", server_default="Brouillon")
    internal_owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True, index=True)
    clause_confidentiality = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_incident_notification = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_audit_right = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_business_continuity = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_reversibility = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_data_location = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_subcontracting = Column(Boolean, nullable=False, default=False, server_default="false")
    clause_data_return_destruction = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
