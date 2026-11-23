"""Enforce case-insensitive uniqueness for asset business references.

Revision ID: 0011_asset_ref_ci
Revises: 0010_asset_risk_restrict
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_asset_ref_ci"
down_revision = "0010_asset_risk_restrict"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail safely with actionable diagnostics if legacy duplicates exist.
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
                    'Cannot enforce case-insensitive asset reference uniqueness; resolve duplicates first: %',
                    duplicate_refs;
            END IF;
        END $$;
    """)
    if "uq_assets_reference_ci" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.execute("CREATE UNIQUE INDEX uq_assets_reference_ci ON assets (lower(reference))")


def downgrade() -> None:
    if "uq_assets_reference_ci" in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("assets")}:
        op.drop_index("uq_assets_reference_ci", table_name="assets")
