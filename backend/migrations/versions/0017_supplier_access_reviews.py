"""Add immutable periodic reviews for supplier access authorizations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_supplier_access_reviews"
down_revision = "0016_supplier_access_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_access_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("access_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("supplier_access_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=False),
        sa.Column("previous_access_level", sa.String(20), nullable=False),
        sa.Column("previous_data_access", sa.Boolean(), nullable=False),
        sa.Column("resulting_access_level", sa.String(20), nullable=False),
        sa.Column("resulting_data_access", sa.Boolean(), nullable=False),
        sa.Column("next_review_at", sa.Date(), nullable=True),
        sa.CheckConstraint("outcome IN ('Maintenue', 'Réduite', 'Révoquée')", name="ck_supplier_access_reviews_outcome"),
        sa.CheckConstraint("previous_access_level IN ('Standard', 'Privilégié')", name="ck_supplier_access_reviews_previous_level"),
        sa.CheckConstraint("resulting_access_level IN ('Standard', 'Privilégié')", name="ck_supplier_access_reviews_resulting_level"),
    )
    op.create_index("ix_supplier_access_reviews_access_request_id", "supplier_access_reviews", ["access_request_id"])
    op.create_index("ix_supplier_access_reviews_reviewed_by_id", "supplier_access_reviews", ["reviewed_by_id"])
    op.create_index("ix_supplier_access_reviews_request_reviewed", "supplier_access_reviews", ["access_request_id", "reviewed_at"])


def downgrade() -> None:
    op.drop_table("supplier_access_reviews")
