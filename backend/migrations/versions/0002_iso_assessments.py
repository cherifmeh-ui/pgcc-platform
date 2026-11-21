"""Add auditable ISO control assessments.

Revision ID: 0002_iso_assessments
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_iso_assessments"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "iso_control_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("control_id", sa.Integer(), nullable=False),
        sa.Column("assessed_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicability", sa.String(length=20), nullable=False),
        sa.Column("implementation_status", sa.String(length=30), nullable=False),
        sa.Column("maturity_level", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("gap_description", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("applicability IN ('Applicable', 'Non applicable')", name="ck_iso_assessment_applicability"),
        sa.CheckConstraint("implementation_status IN ('Non démarré', 'En cours', 'Implémenté', 'Partiellement implémenté')", name="ck_iso_assessment_status"),
        sa.CheckConstraint("maturity_level >= 0 AND maturity_level <= 5", name="ck_iso_assessment_maturity"),
        sa.ForeignKeyConstraint(["control_id"], ["iso_controls.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assessed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_iso_control_assessments_control_id", "iso_control_assessments", ["control_id"])
    op.create_index("ix_iso_control_assessments_assessed_by_id", "iso_control_assessments", ["assessed_by_id"])
    op.create_index("ix_iso_control_assessments_assessed_at", "iso_control_assessments", ["assessed_at"])


def downgrade() -> None:
    op.drop_index("ix_iso_control_assessments_assessed_at", table_name="iso_control_assessments")
    op.drop_index("ix_iso_control_assessments_assessed_by_id", table_name="iso_control_assessments")
    op.drop_index("ix_iso_control_assessments_control_id", table_name="iso_control_assessments")
    op.drop_table("iso_control_assessments")
