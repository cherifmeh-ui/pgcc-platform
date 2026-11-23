"""Allow multiple technical assets to reference one application.

Revision ID: 0008_asset_app_cardinality
Revises: 0007_asset_risk_links
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_asset_app_cardinality"
down_revision = "0007_asset_risk_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("assets"):
        return
    for constraint in inspector.get_unique_constraints("assets"):
        if constraint.get("column_names") == ["application_id"] and constraint.get("name"):
            op.drop_constraint(constraint["name"], "assets", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("assets"):
        return
    existing = inspector.get_unique_constraints("assets")
    if any(item.get("column_names") == ["application_id"] for item in existing):
        return
    duplicate = bind.execute(sa.text(
        "SELECT application_id FROM assets WHERE application_id IS NOT NULL "
        "GROUP BY application_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Cannot downgrade 0008: multiple assets reference the same application.")
    op.create_unique_constraint("uq_assets_application_id", "assets", ["application_id"])
