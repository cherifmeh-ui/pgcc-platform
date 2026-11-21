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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("action_items")}
    if "iso_control_id" not in columns:
        op.add_column("action_items", sa.Column("iso_control_id", sa.Integer(), nullable=True))
    if "iso_assessment_id" not in columns:
        op.add_column("action_items", sa.Column("iso_assessment_id", postgresql.UUID(as_uuid=True), nullable=True))

    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("action_items")}
    if "fk_action_items_iso_control_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_action_items_iso_control_id",
            "action_items", "iso_controls",
            ["iso_control_id"], ["id"], ondelete="RESTRICT",
        )
    if "fk_action_items_iso_assessment_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_action_items_iso_assessment_id",
            "action_items", "iso_control_assessments",
            ["iso_assessment_id"], ["id"], ondelete="RESTRICT",
        )

    indexes = {index["name"] for index in inspector.get_indexes("action_items")}
    if "ix_action_items_iso_control_id" not in indexes:
        op.create_index("ix_action_items_iso_control_id", "action_items", ["iso_control_id"])
    if "ix_action_items_iso_assessment_id" not in indexes:
        op.create_index("ix_action_items_iso_assessment_id", "action_items", ["iso_assessment_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("action_items")}
    if "ix_action_items_iso_assessment_id" in indexes:
        op.drop_index("ix_action_items_iso_assessment_id", table_name="action_items")
    if "ix_action_items_iso_control_id" in indexes:
        op.drop_index("ix_action_items_iso_control_id", table_name="action_items")
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("action_items")}
    if "fk_action_items_iso_assessment_id" in foreign_keys:
        op.drop_constraint("fk_action_items_iso_assessment_id", "action_items", type_="foreignkey")
    if "fk_action_items_iso_control_id" in foreign_keys:
        op.drop_constraint("fk_action_items_iso_control_id", "action_items", type_="foreignkey")
    columns = {column["name"] for column in inspector.get_columns("action_items")}
    if "iso_assessment_id" in columns:
        op.drop_column("action_items", "iso_assessment_id")
    if "iso_control_id" in columns:
        op.drop_column("action_items", "iso_control_id")
