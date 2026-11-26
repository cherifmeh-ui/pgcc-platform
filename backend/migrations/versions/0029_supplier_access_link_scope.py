"""Enforce supplier/asset identity consistency for supplier access requests.

Revision ID: 0029_supplier_access_link_scope
Revises: 0028_document_acl
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_supplier_access_link_scope"
down_revision = "0028_document_acl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Do not silently rewrite historical access decisions. Stop with a
    # diagnostic if denormalized references disagree with their source link.
    mismatches = bind.execute(sa.text("""
        SELECT count(*)
        FROM supplier_access_requests AS request
        LEFT JOIN supplier_asset_links AS link
          ON link.id = request.supplier_asset_link_id
        WHERE link.id IS NULL
           OR link.supplier_id IS DISTINCT FROM request.supplier_id
           OR link.asset_id IS DISTINCT FROM request.asset_id
    """)).scalar_one()
    if mismatches:
        raise RuntimeError(
            f"{mismatches} supplier access request(s) reference a supplier/asset "
            "different from their supplier-asset link; reconcile these records before migration."
        )

    unique_constraints = {
        item["name"] for item in inspector.get_unique_constraints("supplier_asset_links")
    }
    if "uq_supplier_asset_link_scope" not in unique_constraints:
        op.create_unique_constraint(
            "uq_supplier_asset_link_scope",
            "supplier_asset_links",
            ["id", "supplier_id", "asset_id"],
        )

    foreign_keys = inspector.get_foreign_keys("supplier_access_requests")
    for foreign_key in foreign_keys:
        if (
            foreign_key.get("referred_table") == "supplier_asset_links"
            and foreign_key.get("constrained_columns") == ["supplier_asset_link_id"]
            and foreign_key.get("name")
        ):
            op.drop_constraint(
                foreign_key["name"], "supplier_access_requests", type_="foreignkey"
            )

    current_names = {
        item.get("name") for item in sa.inspect(bind).get_foreign_keys("supplier_access_requests")
    }
    if "fk_supplier_access_requests_link_scope" not in current_names:
        op.create_foreign_key(
            "fk_supplier_access_requests_link_scope",
            "supplier_access_requests",
            "supplier_asset_links",
            ["supplier_asset_link_id", "supplier_id", "asset_id"],
            ["id", "supplier_id", "asset_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    bind = op.get_bind()
    foreign_keys = sa.inspect(bind).get_foreign_keys("supplier_access_requests")
    composite = next(
        (
            item for item in foreign_keys
            if item.get("name") == "fk_supplier_access_requests_link_scope"
        ),
        None,
    )
    if composite:
        op.drop_constraint(
            "fk_supplier_access_requests_link_scope",
            "supplier_access_requests",
            type_="foreignkey",
        )

    foreign_keys = sa.inspect(bind).get_foreign_keys("supplier_access_requests")
    if not any(
        item.get("referred_table") == "supplier_asset_links"
        and item.get("constrained_columns") == ["supplier_asset_link_id"]
        for item in foreign_keys
    ):
        op.create_foreign_key(
            "supplier_access_requests_supplier_asset_link_id_fkey",
            "supplier_access_requests",
            "supplier_asset_links",
            ["supplier_asset_link_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    unique_constraints = {
        item["name"] for item in sa.inspect(bind).get_unique_constraints("supplier_asset_links")
    }
    if "uq_supplier_asset_link_scope" in unique_constraints:
        op.drop_constraint(
            "uq_supplier_asset_link_scope", "supplier_asset_links", type_="unique"
        )
