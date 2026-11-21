"""Link corrective actions to ISO control assessments.

Revision ID: 0004_action_iso_links
Revises: 0003_iso_evidence
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_action_iso_links"
down_revision = "0003_iso_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("action_items", sa.Column("iso_control_id", sa.Integer(), nullable=True))
    op.add_column("action_items", sa.Column("iso_assessment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_action_items_iso_control_id",
        "action_items", "iso_controls",
        ["iso_control_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_action_items_iso_assessment_id",
        "action_items", "iso_control_assessments",
        ["iso_assessment_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_action_items_iso_control_id", "action_items", ["iso_control_id"])
    op.create_index("ix_action_items_iso_assessment_id", "action_items", ["iso_assessment_id"])


def downgrade() -> None:
    op.drop_index("ix_action_items_iso_assessment_id", table_name="action_items")
    op.drop_index("ix_action_items_iso_control_id", table_name="action_items")
    op.drop_constraint("fk_action_items_iso_assessment_id", "action_items", type_="foreignkey")
    op.drop_constraint("fk_action_items_iso_control_id", "action_items", type_="foreignkey")
    op.drop_column("action_items", "iso_assessment_id")
    op.drop_column("action_items", "iso_control_id")
