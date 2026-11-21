"""Add indexes supporting common asset inventory filters.

Revision ID: 0009_asset_inventory_filter_indexes
Revises: 0008_asset_application_cardinality
"""
from alembic import op

revision = "0009_asset_inventory_filter_indexes"
down_revision = "0008_asset_application_cardinality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_assets_owner", "assets", ["owner"], unique=False)
    op.create_index("ix_assets_location", "assets", ["location"], unique=False)
    op.create_index("ix_assets_lifecycle_status", "assets", ["lifecycle_status"], unique=False)
    op.create_index("ix_assets_criticality", "assets", ["criticality"], unique=False)
    op.create_index("ix_assets_classification", "assets", ["classification"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assets_classification", table_name="assets")
    op.drop_index("ix_assets_criticality", table_name="assets")
    op.drop_index("ix_assets_lifecycle_status", table_name="assets")
    op.drop_index("ix_assets_location", table_name="assets")
    op.drop_index("ix_assets_owner", table_name="assets")
