"""Create supplier register and contact tables.

Revision ID: 0012_supplier_register
Revises: 0011_asset_ref_ci
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_supplier_register"
down_revision = "0011_asset_ref_ci"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("suppliers"):
        op.create_table(
            "suppliers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("legal_name", sa.String(length=200), nullable=False),
            sa.Column("trade_name", sa.String(length=200), nullable=True),
            sa.Column("country", sa.String(length=100), nullable=True),
            sa.Column("service_category", sa.String(length=100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("business_owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("direction", sa.String(length=100), nullable=True),
            sa.Column("criticality", sa.String(length=20), server_default="Moyenne", nullable=False),
            sa.Column("dependency_level", sa.String(length=20), server_default="Moyenne", nullable=False),
            sa.Column("data_categories", sa.Text(), nullable=True),
            sa.Column("hosting_location", sa.String(length=200), nullable=True),
            sa.Column("uses_subprocessors", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("status", sa.String(length=40), server_default="À qualifier", nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("criticality IN ('Faible', 'Moyenne', 'Élevée', 'Critique')", name="ck_suppliers_criticality"),
            sa.CheckConstraint("dependency_level IN ('Faible', 'Moyenne', 'Élevée', 'Critique')", name="ck_suppliers_dependency_level"),
            sa.CheckConstraint("status IN ('À qualifier', 'En évaluation', 'Approuvé', 'Approuvé sous conditions', 'Suspendu', 'Terminé')", name="ck_suppliers_status"),
            sa.UniqueConstraint("code", name="uq_suppliers_code"),
        )
    if "ix_suppliers_code" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_code", "suppliers", ["code"])
    if "ix_suppliers_legal_name" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_legal_name", "suppliers", ["legal_name"])
    if "ix_suppliers_service_category" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_service_category", "suppliers", ["service_category"])
    if "ix_suppliers_business_owner_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_business_owner_id", "suppliers", ["business_owner_id"])
    if "ix_suppliers_direction" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_direction", "suppliers", ["direction"])
    if "ix_suppliers_criticality" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_criticality", "suppliers", ["criticality"])
    if "ix_suppliers_status" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_status", "suppliers", ["status"])
    if "ix_suppliers_archived_at" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_archived_at", "suppliers", ["archived_at"])
    if "uq_suppliers_code_ci" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("uq_suppliers_code_ci", "suppliers", [sa.text("lower(code)")], unique=True)
    if "ix_suppliers_active_criticality" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("suppliers")}:
        op.create_index("ix_suppliers_active_criticality", "suppliers", ["archived_at", "criticality"])

    if not sa.inspect(op.get_bind()).has_table("supplier_contacts"):
        op.create_table(
            "supplier_contacts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("full_name", sa.String(length=150), nullable=False),
            sa.Column("role", sa.String(length=100), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("contact_type", sa.String(length=20), server_default="Autre", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("contact_type IN ('Commercial', 'Technique', 'Sécurité', 'Contractuel', 'Autre')", name="ck_supplier_contacts_type"),
        )
    if "ix_supplier_contacts_supplier_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_contacts")}:
        op.create_index("ix_supplier_contacts_supplier_id", "supplier_contacts", ["supplier_id"])
    if "ix_supplier_contacts_supplier_active" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_contacts")}:
        op.create_index("ix_supplier_contacts_supplier_active", "supplier_contacts", ["supplier_id", "is_active"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("supplier_contacts"):
        op.drop_table("supplier_contacts")
    if inspector.has_table("suppliers"):
        op.drop_table("suppliers")
