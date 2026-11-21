"""Align asset type and normalized reference constraints with the model.

Revision ID: 0020_asset_reference_and_type_constraints
Revises: 0019_supplier_risk_snapshots
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_asset_reference_and_type_constraints"
down_revision = "0019_supplier_risk_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE duplicate_refs TEXT;
        BEGIN
            SELECT string_agg(reference_group, ', ')
            INTO duplicate_refs
            FROM (
                SELECT string_agg(reference, ' / ' ORDER BY reference) AS reference_group
                FROM assets
                GROUP BY lower(btrim(reference))
                HAVING count(*) > 1
                LIMIT 20
            ) duplicates;
            IF duplicate_refs IS NOT NULL THEN
                RAISE EXCEPTION
                    'Cannot enforce normalized asset reference uniqueness; resolve duplicates first: %',
                    duplicate_refs;
            END IF;
        END $$;
    """)
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}
    if "uq_assets_reference_ci" in indexes:
        op.drop_index("uq_assets_reference_ci", table_name="assets")
    op.create_index(
        "uq_assets_reference_ci",
        "assets",
        [sa.text("lower(btrim(reference))")],
        unique=True,
    )

    checks = {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints("assets")}
    if "ck_assets_reference_nonblank" not in checks:
        op.create_check_constraint(
            "ck_assets_reference_nonblank",
            "assets",
            "btrim(reference) <> ''",
        )
    if "ck_assets_asset_type" in checks:
        op.drop_constraint("ck_assets_asset_type", "assets", type_="check")
    op.create_check_constraint(
        "ck_assets_asset_type",
        "assets",
        "asset_type IN ('process', 'information', 'application', 'hardware', "
        "'software', 'infrastructure', 'network', 'service', 'cloud_resource', "
        "'facility', 'other')",
    )


def downgrade() -> None:
    op.execute("""
        DO $pgcc$
        BEGIN
            IF EXISTS (SELECT 1 FROM assets WHERE asset_type = 'cloud_resource') THEN
                RAISE EXCEPTION
                    'Cannot downgrade asset type constraint while cloud_resource assets exist; migrate those records first';
            END IF;
        END $pgcc$;
    """)
    checks = {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints("assets")}
    if "ck_assets_asset_type" in checks:
        op.drop_constraint("ck_assets_asset_type", "assets", type_="check")
    op.create_check_constraint(
        "ck_assets_asset_type",
        "assets",
        "asset_type IN ('process', 'information', 'application', 'hardware', "
        "'software', 'infrastructure', 'network', 'service', 'facility', 'other')",
    )
    checks = {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints("assets")}
    if "ck_assets_reference_nonblank" in checks:
        op.drop_constraint("ck_assets_reference_nonblank", "assets", type_="check")
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}
    if "uq_assets_reference_ci" in indexes:
        op.drop_index("uq_assets_reference_ci", table_name="assets")
    op.create_index(
        "uq_assets_reference_ci",
        "assets",
        [sa.text("lower(reference)")],
        unique=True,
    )
