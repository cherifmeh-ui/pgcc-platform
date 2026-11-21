"""Add supplier contracts and security clauses.

Revision ID: 0013_supplier_contracts
Revises: 0012_supplier_register
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_supplier_contracts"
down_revision = "0012_supplier_register"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("contract_type", sa.String(30), server_default="Service", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notice_period_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(30), server_default="Brouillon", nullable=False),
        sa.Column("internal_owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("clause_confidentiality", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_incident_notification", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_audit_right", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_business_continuity", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_reversibility", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_data_location", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_subcontracting", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clause_data_return_destruction", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("contract_type IN ('Service', 'Maintenance', 'Hébergement', 'Infogérance', 'Licence', 'Autre')", name="ck_supplier_contracts_type"),
        sa.CheckConstraint("status IN ('Brouillon', 'En validation', 'Actif', 'À renouveler', 'Expiré', 'Résilié')", name="ck_supplier_contracts_status"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_supplier_contracts_dates"),
        sa.CheckConstraint("notice_period_days >= 0 AND notice_period_days <= 3650", name="ck_supplier_contracts_notice"),
        sa.UniqueConstraint("supplier_id", "reference", name="uq_supplier_contracts_supplier_reference"),
    )
    op.create_index("ix_supplier_contracts_supplier_id", "supplier_contracts", ["supplier_id"])
    op.create_index("ix_supplier_contracts_internal_owner_id", "supplier_contracts", ["internal_owner_id"])
    op.create_index("ix_supplier_contracts_document_id", "supplier_contracts", ["document_id"])
    op.create_index("uq_supplier_contract_reference_ci", "supplier_contracts", ["supplier_id", sa.text("lower(reference)")], unique=True)
    op.create_index("ix_supplier_contracts_supplier_status_end", "supplier_contracts", ["supplier_id", "status", "end_date"])


def downgrade() -> None:
    op.drop_table("supplier_contracts")
