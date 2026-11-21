"""Add explicit asset-risk association.

Revision ID: 0007_asset_risk_links
Revises: 0006_asset_inventory
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_asset_risk_links"
down_revision = "0006_asset_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("asset_risk_links"):
        op.create_table(
            "asset_risk_links",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("risk_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("relationship_context", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["risk_id"], ["risks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("asset_id", "risk_id", name="uq_asset_risk_link"),
        )
        indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("asset_risk_links")}
    if "ix_asset_risk_links_asset_id" not in indexes:
        op.create_index("ix_asset_risk_links_asset_id", "asset_risk_links", ["asset_id"], unique=False)
    if "ix_asset_risk_links_risk_id" not in indexes:
        op.create_index("ix_asset_risk_links_risk_id", "asset_risk_links", ["risk_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("asset_risk_links"):
        indexes = {item["name"] for item in inspector.get_indexes("asset_risk_links")}
        if "ix_asset_risk_links_risk_id" in indexes:
            op.drop_index("ix_asset_risk_links_risk_id", table_name="asset_risk_links")
        if "ix_asset_risk_links_asset_id" in indexes:
            op.drop_index("ix_asset_risk_links_asset_id", table_name="asset_risk_links")
        op.drop_table("asset_risk_links")
