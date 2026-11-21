"""Asset inventory and dependency graph models for PGCC."""
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('process', 'information', 'application', 'hardware', "
            "'software', 'infrastructure', 'network', 'service', 'cloud_resource', "
            "'facility', 'other')",
            name="ck_assets_asset_type",
        ),
        CheckConstraint(
            "criticality IN ('Faible', 'Moyenne', 'Élevée', 'Critique')",
            name="ck_assets_criticality",
        ),
        CheckConstraint(
            "lifecycle_status IN ('Identifié', 'Actif', 'En maintenance', "
            "'En projet', 'Retiré', 'Décommissionné')",
            name="ck_assets_lifecycle_status",
        ),
        CheckConstraint(
            "confidentiality IN ('Faible', 'Moyenne', 'Élevée', 'Critique') "
            "OR confidentiality IS NULL",
            name="ck_assets_confidentiality",
        ),
        CheckConstraint(
            "integrity IN ('Faible', 'Moyenne', 'Élevée', 'Critique') OR integrity IS NULL",
            name="ck_assets_integrity",
        ),
        CheckConstraint(
            "availability IN ('Faible', 'Moyenne', 'Élevée', 'Critique') OR availability IS NULL",
            name="ck_assets_availability",
        ),
        UniqueConstraint("reference", name="uq_assets_reference"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    reference = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    asset_type = Column(String(30), nullable=False, default="other")
    application_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    owner = Column(String(150), nullable=True, index=True)
    custodian = Column(String(150), nullable=True)
    direction = Column(String(100), nullable=True, index=True)
    location = Column(String(200), nullable=True, index=True)
    lifecycle_status = Column(String(30), nullable=False, default="Identifié", index=True)
    criticality = Column(String(20), nullable=False, default="Moyenne", index=True)
    confidentiality = Column(String(20), nullable=True)
    integrity = Column(String(20), nullable=True)
    availability = Column(String(20), nullable=True)
    classification = Column(String(100), nullable=True, index=True)
    hostname = Column(String(255), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    fqdn = Column(String(255), nullable=True)
    operating_system = Column(String(150), nullable=True)
    version = Column(String(100), nullable=True)
    manufacturer = Column(String(150), nullable=True)
    model = Column(String(150), nullable=True)
    serial_number = Column(String(150), nullable=True, index=True)
    discovery_source = Column(String(100), nullable=True)
    source_reference = Column(String(255), nullable=True)
    last_inventory_date = Column(DateTime(timezone=True), nullable=True)
    end_of_support_date = Column(DateTime(timezone=True), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    retired_at = Column(DateTime(timezone=True), nullable=True)


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        CheckConstraint("source_asset_id <> target_asset_id", name="ck_asset_relationship_not_self"),
        CheckConstraint(
            "relationship_type IN ('depends_on', 'hosts', 'connects_to', 'stores', "
            "'processes', 'supports', 'contains', 'communicates_with', 'supplied_by', 'other')",
            name="ck_asset_relationship_type",
        ),
        UniqueConstraint(
            "source_asset_id", "target_asset_id", "relationship_type",
            name="uq_asset_relationship_pair_type",
        ),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_asset_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_asset_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    relationship_type = Column(String(30), nullable=False)
    description = Column(String(500), nullable=True)
    criticality = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)


class AssetRiskLink(Base):
    """Explicit association between an asset and an information-security risk."""
    __tablename__ = "asset_risk_links"
    __table_args__ = (
        UniqueConstraint("asset_id", "risk_id", name="uq_asset_risk_link"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    risk_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_context = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)
