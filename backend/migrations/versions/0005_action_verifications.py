"""Add corrective action effectiveness verification history.

Revision ID: 0005_action_verifications
Revises: 0004_action_iso_links
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_action_verifications"
down_revision = "0004_action_iso_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "action_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('Effective', 'Ineffective', 'Follow-up required')", name="ck_action_verification_outcome"),
        sa.ForeignKeyConstraint(["action_id"], ["action_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_verifications_action_id", "action_verifications", ["action_id"])
    op.create_index("ix_action_verifications_verified_by_id", "action_verifications", ["verified_by_id"])
    op.create_index("ix_action_verifications_evidence_document_id", "action_verifications", ["evidence_document_id"])


def downgrade() -> None:
    op.drop_index("ix_action_verifications_evidence_document_id", table_name="action_verifications")
    op.drop_index("ix_action_verifications_verified_by_id", table_name="action_verifications")
    op.drop_index("ix_action_verifications_action_id", table_name="action_verifications")
    op.drop_table("action_verifications")
