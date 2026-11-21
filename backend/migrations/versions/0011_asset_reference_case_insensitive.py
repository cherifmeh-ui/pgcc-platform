"""Enforce case-insensitive uniqueness for asset business references.

Revision ID: 0011_asset_reference_case_insensitive
Revises: 0010_asset_risk_restrict_delete
"""
from alembic import op

revision = "0011_asset_reference_case_insensitive"
down_revision = "0010_asset_risk_restrict_delete"
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
    op.execute(
        "CREATE UNIQUE INDEX uq_assets_reference_ci ON assets (lower(reference))"
    )


def downgrade() -> None:
    op.drop_index("uq_assets_reference_ci", table_name="assets")
