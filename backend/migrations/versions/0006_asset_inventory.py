"""Create asset inventory and dependency graph tables.

Revision ID: 0006_asset_inventory
Revises: 0005_action_verifications
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_asset_inventory"
down_revision = "0005_action_verifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("assets"):
        op.create_table(
            "assets",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reference", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("asset_type", sa.String(length=30), nullable=False),
            sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("owner", sa.String(length=150), nullable=True),
            sa.Column("custodian", sa.String(length=150), nullable=True),
            sa.Column("direction", sa.String(length=100), nullable=True),
            sa.Column("location", sa.String(length=200), nullable=True),
            sa.Column("lifecycle_status", sa.String(length=30), nullable=False),
            sa.Column("criticality", sa.String(length=20), nullable=False),
            sa.Column("confidentiality", sa.String(length=20), nullable=True),
            sa.Column("integrity", sa.String(length=20), nullable=True),
            sa.Column("availability", sa.String(length=20), nullable=True),
            sa.Column("classification", sa.String(length=100), nullable=True),
            sa.Column("hostname", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("fqdn", sa.String(length=255), nullable=True),
            sa.Column("operating_system", sa.String(length=150), nullable=True),
            sa.Column("version", sa.String(length=100), nullable=True),
            sa.Column("manufacturer", sa.String(length=150), nullable=True),
            sa.Column("model", sa.String(length=150), nullable=True),
            sa.Column("serial_number", sa.String(length=150), nullable=True),
            sa.Column("discovery_source", sa.String(length=100), nullable=True),
            sa.Column("source_reference", sa.String(length=255), nullable=True),
            sa.Column("last_inventory_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("end_of_support_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "asset_type IN ('process', 'information', 'application', 'hardware', 'software', "
                "'infrastructure', 'network', 'service', 'cloud_resource', 'facility', 'other')",
                name="ck_assets_asset_type",
            ),
            sa.CheckConstraint(
                "criticality IN ('Faible', 'Moyenne', 'Élevée', 'Critique')",
                name="ck_assets_criticality",
            ),
            sa.CheckConstraint(
                "lifecycle_status IN ('Identifié', 'Actif', 'En maintenance', 'En projet', 'Retiré', 'Décommissionné')",
                name="ck_assets_lifecycle_status",
            ),
            sa.CheckConstraint(
                "confidentiality IN ('Faible', 'Moyenne', 'Élevée', 'Critique') OR confidentiality IS NULL",
                name="ck_assets_confidentiality",
            ),
            sa.CheckConstraint(
                "integrity IN ('Faible', 'Moyenne', 'Élevée', 'Critique') OR integrity IS NULL",
                name="ck_assets_integrity",
            ),
            sa.CheckConstraint(
                "availability IN ('Faible', 'Moyenne', 'Élevée', 'Critique') OR availability IS NULL",
                name="ck_assets_availability",
            ),
            sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("reference", name="uq_assets_reference"),
            sa.UniqueConstraint("application_id", name="uq_assets_application_id"),
        )
    if "ix_assets_reference" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_reference", "assets", ["reference"], unique=False)
    if "ix_assets_name" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_name", "assets", ["name"], unique=False)
    if "ix_assets_application_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_application_id", "assets", ["application_id"], unique=False)
    if "ix_assets_direction" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_direction", "assets", ["direction"], unique=False)
    if "ix_assets_hostname" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_hostname", "assets", ["hostname"], unique=False)
    if "ix_assets_serial_number" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_serial_number", "assets", ["serial_number"], unique=False)

    if not sa.inspect(op.get_bind()).has_table("asset_relationships"):
        op.create_table(
            "asset_relationships",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("target_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("relationship_type", sa.String(length=30), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("criticality", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.CheckConstraint("source_asset_id <> target_asset_id", name="ck_asset_relationship_not_self"),
            sa.CheckConstraint(
                "relationship_type IN ('depends_on', 'hosts', 'connects_to', 'stores', 'processes', "
                "'supports', 'contains', 'communicates_with', 'supplied_by', 'other')",
                name="ck_asset_relationship_type",
            ),
            sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["target_asset_id"], ["assets.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_asset_id", "target_asset_id", "relationship_type", name="uq_asset_relationship_pair_type"),
        )
    if "ix_asset_relationships_source_asset_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("asset_relationships")}:
        op.create_index("ix_asset_relationships_source_asset_id", "asset_relationships", ["source_asset_id"], unique=False)
    if "ix_asset_relationships_target_asset_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("asset_relationships")}:
        op.create_index("ix_asset_relationships_target_asset_id", "asset_relationships", ["target_asset_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("asset_relationships"):
        indexes = {item["name"] for item in inspector.get_indexes("asset_relationships")}
        if "ix_asset_relationships_target_asset_id" in indexes:
            op.drop_index("ix_asset_relationships_target_asset_id", table_name="asset_relationships")
        if "ix_asset_relationships_source_asset_id" in indexes:
            op.drop_index("ix_asset_relationships_source_asset_id", table_name="asset_relationships")
        op.drop_table("asset_relationships")
    if inspector.has_table("assets"):
        indexes = {item["name"] for item in inspector.get_indexes("assets")}
        for index_name in ["ix_assets_serial_number", "ix_assets_hostname", "ix_assets_direction", "ix_assets_application_id", "ix_assets_name", "ix_assets_reference"]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="assets")
        op.drop_table("assets")
