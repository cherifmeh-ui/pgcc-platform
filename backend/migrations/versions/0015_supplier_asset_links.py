"""Add traceable supplier-to-asset relationships."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_supplier_asset_links"
down_revision = "0014_supplier_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_asset_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column("access_level", sa.String(20), server_default="Aucun", nullable=False),
        sa.Column("data_access", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("scope", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), server_default="Actif", nullable=False),
        sa.Column("review_due_at", sa.Date(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("relationship_type IN ('Héberge', 'Maintient', 'Administre', 'Accède', 'Fournit', 'Autre')", name="ck_supplier_asset_links_type"),
        sa.CheckConstraint("access_level IN ('Aucun', 'Standard', 'Privilégié')", name="ck_supplier_asset_links_access"),
        sa.CheckConstraint("status IN ('Actif', 'Suspendu', 'Terminé')", name="ck_supplier_asset_links_status"),
        sa.UniqueConstraint("supplier_id", "asset_id", "relationship_type", name="uq_supplier_asset_link"),
    )
    op.create_index("ix_supplier_asset_links_supplier_id", "supplier_asset_links", ["supplier_id"])
    op.create_index("ix_supplier_asset_links_asset_id", "supplier_asset_links", ["asset_id"])
    op.create_index("ix_supplier_asset_links_asset_status", "supplier_asset_links", ["asset_id", "status"])


def downgrade() -> None:
    op.drop_table("supplier_asset_links")
