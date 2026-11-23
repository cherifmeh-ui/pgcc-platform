"""Add indexes supporting common asset inventory filters.

Revision ID: 0009_asset_inventory_filter_indexes
Revises: 0008_asset_app_cardinality
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_asset_inventory_filter_indexes"
down_revision = "0008_asset_app_cardinality"
branch_labels = None
depends_on = None

def upgrade() -> None:
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}
    for name, column in (
        ("ix_assets_owner", "owner"),
        ("ix_assets_location", "location"),
        ("ix_assets_lifecycle_status", "lifecycle_status"),
        ("ix_assets_criticality", "criticality"),
        ("ix_assets_classification", "classification"),
    ):
        if name not in indexes:
            op.create_index(name, "assets", [column], unique=False)

def downgrade() -> None:
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}
    for name in (
        "ix_assets_classification",
        "ix_assets_criticality",
        "ix_assets_lifecycle_status",
        "ix_assets_location",
        "ix_assets_owner",
    ):
        if name in indexes:
            op.drop_index(name, table_name="assets")
