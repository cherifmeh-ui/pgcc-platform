"""Add ISO control evidence records.

Revision ID: 0003_iso_evidence
Revises: 0002_iso_assessments
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_iso_evidence"
down_revision = "0002_iso_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "iso_control_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_owner", sa.String(length=150), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("verification_status IN ('Pending', 'Verified', 'Rejected')", name="ck_iso_evidence_verification_status"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until >= collected_at", name="ck_iso_evidence_validity_dates"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_iso_evidence_sha256_length"),
        sa.ForeignKeyConstraint(["control_id"], ["iso_controls.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assessment_id"], ["iso_control_assessments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "control_id", name="uq_iso_evidence_document_control"),
    )
    op.create_index("ix_iso_control_evidence_control_id", "iso_control_evidence", ["control_id"])
    op.create_index("ix_iso_control_evidence_document_id", "iso_control_evidence", ["document_id"])
    op.create_index("ix_iso_control_evidence_assessment_id", "iso_control_evidence", ["assessment_id"])


def downgrade() -> None:
    op.drop_index("ix_iso_control_evidence_assessment_id", table_name="iso_control_evidence")
    op.drop_index("ix_iso_control_evidence_document_id", table_name="iso_control_evidence")
    op.drop_index("ix_iso_control_evidence_control_id", table_name="iso_control_evidence")
    op.drop_table("iso_control_evidence")
