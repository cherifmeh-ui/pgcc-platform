"""Prevent physical deletion of risks linked to assets.

Revision ID: 0010_asset_risk_restrict_delete
Revises: 0009_asset_inventory_filter_indexes
"""
from alembic import op

revision = "0010_asset_risk_restrict_delete"
down_revision = "0009_asset_inventory_filter_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "asset_risk_links_risk_id_fkey",
        "asset_risk_links",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "asset_risk_links_risk_id_fkey",
        "asset_risk_links",
        "risks",
        ["risk_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Restores the previous behavior; only use if explicitly required.
    op.drop_constraint(
        "asset_risk_links_risk_id_fkey",
        "asset_risk_links",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "asset_risk_links_risk_id_fkey",
        "asset_risk_links",
        "risks",
        ["risk_id"],
        ["id"],
        ondelete="CASCADE",
    )
