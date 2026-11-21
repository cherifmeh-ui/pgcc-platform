"""Prevent physical deletion of risks linked to assets.

Revision ID: 0010_asset_risk_restrict_delete
Revises: 0009_asset_inventory_filter_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_asset_risk_restrict_delete"
down_revision = "0009_asset_inventory_filter_indexes"
branch_labels = None
depends_on = None


def _risk_fk():
    inspector = sa.inspect(op.get_bind())
    return next((fk for fk in inspector.get_foreign_keys("asset_risk_links") if fk.get("constrained_columns") == ["risk_id"] and fk.get("referred_table") == "risks"), None)


def upgrade() -> None:
    fk = _risk_fk()
    if fk and fk.get("options", {}).get("ondelete", "").upper() != "RESTRICT":
        op.drop_constraint(fk["name"], "asset_risk_links", type_="foreignkey")
        op.create_foreign_key("asset_risk_links_risk_id_fkey", "asset_risk_links", "risks", ["risk_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    fk = _risk_fk()
    if fk and fk.get("options", {}).get("ondelete", "").upper() != "CASCADE":
        op.drop_constraint(fk["name"], "asset_risk_links", type_="foreignkey")
        op.create_foreign_key("asset_risk_links_risk_id_fkey", "asset_risk_links", "risks", ["risk_id"], ["id"], ondelete="CASCADE")
