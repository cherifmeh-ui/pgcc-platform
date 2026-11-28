"""Third-party supplier register models (TPRM)."""
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, ForeignKeyConstraint, Numeric, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

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

class SupplierAssessment(Base):
    """Immutable, versioned supplier security assessment after submission."""
    __tablename__ = "supplier_assessments"
    __table_args__ = (
        CheckConstraint("assessment_type IN ('Initiale', 'Périodique', 'Renouvellement', 'Incident', 'Changement majeur')", name="ck_supplier_assessments_type"),
        CheckConstraint("status IN ('Brouillon', 'À valider', 'Validée', 'Clôturée')", name="ck_supplier_assessments_status"),
        CheckConstraint("risk_level IS NULL OR risk_level IN ('Faible', 'Moyen', 'Élevé', 'Critique')", name="ck_supplier_assessments_risk"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_supplier_assessments_score"),
        CheckConstraint("(status = 'Brouillon' AND submitted_at IS NULL AND validated_at IS NULL) OR (status = 'À valider' AND submitted_at IS NOT NULL AND validated_at IS NULL) OR (status IN ('Validée', 'Clôturée') AND submitted_at IS NOT NULL AND validated_at IS NOT NULL)", name="ck_supplier_assessments_lifecycle"),
        Index("ix_supplier_assessments_supplier_status", "supplier_id", "status", "created_at"),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    assessment_type = Column(String(30), nullable=False, default="Initiale")
    scope = Column(Text, nullable=False)
    questionnaire_version = Column(String(50), nullable=False)
    questionnaire_snapshot = Column(JSONB, nullable=False)
    answers = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    status = Column(String(20), nullable=False, default="Brouillon", server_default="Brouillon")
    score = Column(Numeric(5, 2), nullable=True)
    risk_level = Column(String(20), nullable=True)
    decision = Column(String(30), nullable=True)
    assessed_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    validated_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    next_review_at = Column(Date, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierAssetLink(Base):
    """Traceable relationship between a supplier and an inventoried asset."""
    __tablename__ = "supplier_asset_links"
    __table_args__ = (
        CheckConstraint("relationship_type IN ('Héberge', 'Maintient', 'Administre', 'Accède', 'Fournit', 'Autre')", name="ck_supplier_asset_links_type"),
        CheckConstraint("access_level IN ('Aucun', 'Standard', 'Privilégié')", name="ck_supplier_asset_links_access"),
        CheckConstraint("status IN ('Actif', 'Suspendu', 'Terminé')", name="ck_supplier_asset_links_status"),
        UniqueConstraint("supplier_id", "asset_id", "relationship_type", name="uq_supplier_asset_link"),
        UniqueConstraint("id", "supplier_id", "asset_id", name="uq_supplier_asset_link_scope"),
        Index("ix_supplier_asset_links_asset_status", "asset_id", "status"),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    relationship_type = Column(String(20), nullable=False)
    access_level = Column(String(20), nullable=False, default="Aucun", server_default="Aucun")
    data_access = Column(Boolean, nullable=False, default=False, server_default="false")
    scope = Column(String(1000), nullable=True)
    status = Column(String(20), nullable=False, default="Actif", server_default="Actif")
    review_due_at = Column(Date, nullable=True)
    created_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierAccessRequest(Base):
    """Time-bound internal authorization decision for a supplier's access to an asset."""
    __tablename__ = "supplier_access_requests"
    __table_args__ = (
        CheckConstraint("access_level IN ('Standard', 'Privilégié')", name="ck_supplier_access_requests_level"),
        CheckConstraint("status IN ('Demandé', 'Approuvé', 'Refusé', 'Suspendu', 'Révoqué', 'Expiré')", name="ck_supplier_access_requests_status"),
        CheckConstraint("end_date >= start_date", name="ck_supplier_access_requests_dates"),
        CheckConstraint("review_due_at >= start_date AND review_due_at <= end_date", name="ck_supplier_access_requests_review_window"),
        CheckConstraint("(status = 'Demandé' AND decided_by_id IS NULL AND decided_at IS NULL) OR (status != 'Demandé' AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL)", name="ck_supplier_access_requests_decision_trace"),
        Index("ix_supplier_access_requests_supplier_status", "supplier_id", "status", "end_date"),
        Index("ix_supplier_access_requests_asset_status", "asset_id", "status", "end_date"),
        Index("uq_supplier_access_requests_open_link", "supplier_asset_link_id", unique=True, postgresql_where=text("status IN ('Demandé', 'Approuvé', 'Suspendu')")),
        ForeignKeyConstraint(
            ["supplier_asset_link_id", "supplier_id", "asset_id"],
            ["supplier_asset_links.id", "supplier_asset_links.supplier_id", "supplier_asset_links.asset_id"],
            name="fk_supplier_access_requests_link_scope",
            ondelete="RESTRICT",
        ),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    supplier_asset_link_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    asset_id = Column(PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    access_level = Column(String(20), nullable=False)
    data_access = Column(Boolean, nullable=False, default=False, server_default="false")
    justification = Column(Text, nullable=False)
    scope = Column(String(1000), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    review_due_at = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="Demandé", server_default="Demandé")
    requested_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_comment = Column(String(2000), nullable=True)
    revoked_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SupplierAccessReview(Base):
    """Immutable audit record of a periodic supplier access review."""
    __tablename__ = "supplier_access_reviews"
    __table_args__ = (
        CheckConstraint("outcome IN ('Maintenue', 'Réduite', 'Révoquée')", name="ck_supplier_access_reviews_outcome"),
        CheckConstraint("previous_access_level IN ('Standard', 'Privilégié')", name="ck_supplier_access_reviews_previous_level"),
        CheckConstraint("resulting_access_level IN ('Standard', 'Privilégié')", name="ck_supplier_access_reviews_resulting_level"),
        Index("ix_supplier_access_reviews_request_reviewed", "access_request_id", "reviewed_at"),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    access_request_id = Column(PG_UUID(as_uuid=True), ForeignKey("supplier_access_requests.id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewed_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    outcome = Column(String(20), nullable=False)
    comment = Column(String(2000), nullable=False)
    previous_access_level = Column(String(20), nullable=False)
    previous_data_access = Column(Boolean, nullable=False)
    resulting_access_level = Column(String(20), nullable=False)
    resulting_data_access = Column(Boolean, nullable=False)
    next_review_at = Column(Date, nullable=True)


class SupplierRiskLink(Base):
    """Traceable link from a supplier dependency to an existing enterprise risk."""
    __tablename__ = "supplier_risk_links"
    __table_args__ = (
        CheckConstraint("relationship_type IN ('Dépendance opérationnelle', 'Hébergement', 'Maintenance', 'Accès aux données', 'Accès privilégié', 'Sous-traitance', 'Autre')", name="ck_supplier_risk_links_type"),
        UniqueConstraint("supplier_id", "risk_id", name="uq_supplier_risk_link"),
    )
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    risk_id = Column(PG_UUID(as_uuid=True), ForeignKey("risks.id", ondelete="RESTRICT"), nullable=False, index=True)
    relationship_type = Column(String(40), nullable=False)
    relationship_context = Column(String(2000), nullable=False)
    created_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupplierRiskSnapshot(Base):
    """Immutable monthly snapshot of consolidated third-party risk indicators."""
    __tablename__ = "supplier_risk_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_month", name="uq_supplier_risk_snapshots_month"),
        Index("ix_supplier_risk_snapshots_month", "snapshot_month"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_month = Column(Date, nullable=False)
    indicators = Column(JSONB, nullable=False)
    captured_by_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
