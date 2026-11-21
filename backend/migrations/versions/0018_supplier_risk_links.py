"""Add supplier-to-existing-risk traceability links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_supplier_risk_links"
down_revision = "0017_supplier_access_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_risk_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("risk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("risks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("relationship_context", sa.String(2000), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("relationship_type IN ('Dépendance opérationnelle', 'Hébergement', 'Maintenance', 'Accès aux données', 'Accès privilégié', 'Sous-traitance', 'Autre')", name="ck_supplier_risk_links_type"),
        sa.UniqueConstraint("supplier_id", "risk_id", name="uq_supplier_risk_link"),
    )
    op.create_index("ix_supplier_risk_links_supplier_id", "supplier_risk_links", ["supplier_id"])
    op.create_index("ix_supplier_risk_links_risk_id", "supplier_risk_links", ["risk_id"])


def downgrade() -> None:
    op.drop_table("supplier_risk_links")
