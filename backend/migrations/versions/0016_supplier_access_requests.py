"""Add traceable, time-bound supplier access requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_supplier_access_requests"
down_revision = "0015_supplier_asset_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_access_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_asset_link_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("supplier_asset_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("access_level", sa.String(20), nullable=False),
        sa.Column("data_access", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(1000), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("review_due_at", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="Demandé", nullable=False),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.String(2000), nullable=True),
        sa.Column("revoked_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("access_level IN ('Standard', 'Privilégié')", name="ck_supplier_access_requests_level"),
        sa.CheckConstraint("status IN ('Demandé', 'Approuvé', 'Refusé', 'Suspendu', 'Révoqué', 'Expiré')", name="ck_supplier_access_requests_status"),
        sa.CheckConstraint("end_date >= start_date", name="ck_supplier_access_requests_dates"),
        sa.CheckConstraint("review_due_at >= start_date AND review_due_at <= end_date", name="ck_supplier_access_requests_review_window"),
        sa.CheckConstraint("(status = 'Demandé' AND decided_by_id IS NULL AND decided_at IS NULL) OR (status != 'Demandé' AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL)", name="ck_supplier_access_requests_decision_trace"),
    )
    op.create_index("ix_supplier_access_requests_supplier_id", "supplier_access_requests", ["supplier_id"])
    op.create_index("ix_supplier_access_requests_supplier_asset_link_id", "supplier_access_requests", ["supplier_asset_link_id"])
    op.create_index("ix_supplier_access_requests_asset_id", "supplier_access_requests", ["asset_id"])
    op.create_index("ix_supplier_access_requests_supplier_status", "supplier_access_requests", ["supplier_id", "status", "end_date"])
    op.create_index("ix_supplier_access_requests_asset_status", "supplier_access_requests", ["asset_id", "status", "end_date"])
    op.create_index("uq_supplier_access_requests_open_link", "supplier_access_requests", ["supplier_asset_link_id"], unique=True, postgresql_where=sa.text("status IN ('Demandé', 'Approuvé', 'Suspendu')"))


def downgrade() -> None:
    op.drop_table("supplier_access_requests")
