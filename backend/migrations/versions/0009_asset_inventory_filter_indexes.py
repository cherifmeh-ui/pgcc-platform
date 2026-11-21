"""Add indexes supporting common asset inventory filters.

Revision ID: 0009_asset_inventory_filter_indexes
Revises: 0008_asset_application_cardinality
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_asset_inventory_filter_indexes"
down_revision = "0008_asset_application_cardinality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "ix_assets_owner" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_owner", "assets", ["owner"], unique=False)
    if "ix_assets_location" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_location", "assets", ["location"], unique=False)
    if "ix_assets_lifecycle_status" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_lifecycle_status", "assets", ["lifecycle_status"], unique=False)
    if "ix_assets_criticality" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_criticality", "assets", ["criticality"], unique=False)
    if "ix_assets_classification" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.create_index("ix_assets_classification", "assets", ["classification"], unique=False)


def downgrade() -> None:
    if "ix_assets_classification" in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.drop_index("ix_assets_classification", table_name="assets")
    if "ix_assets_criticality" in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.drop_index("ix_assets_criticality", table_name="assets")
    if "ix_assets_lifecycle_status" in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.drop_index("ix_assets_lifecycle_status", table_name="assets")
    if "ix_assets_location" in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.drop_index("ix_assets_location", table_name="assets")
    if "ix_assets_owner" in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.drop_index("ix_assets_owner", table_name="assets")
