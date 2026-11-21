"""Allow multiple technical assets to reference one application.

Revision ID: 0008_asset_application_cardinality
Revises: 0007_asset_risk_links
"""
from alembic import op

revision = "0008_asset_application_cardinality"
down_revision = "0007_asset_risk_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_assets_application_id", "assets", type_="unique")


def downgrade() -> None:
    # This downgrade can fail if multiple assets now reference the same application.
    op.create_unique_constraint("uq_assets_application_id", "assets", ["application_id"])
