"""Store immutable monthly snapshots of supplier risk indicators."""
from alembic import op
import sqlalchemy as sa
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_supplier_risk_snapshots"
down_revision = "0018_supplier_risk_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("supplier_risk_snapshots"):
        op.create_table(
            "supplier_risk_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("snapshot_month", sa.Date(), nullable=False),
            sa.Column("indicators", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column(
                "captured_by_id", postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("snapshot_month", name="uq_supplier_risk_snapshots_month"),
        )
    if "ix_supplier_risk_snapshots_month" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_risk_snapshots")}:
        op.create_index(
            "ix_supplier_risk_snapshots_month",
            "supplier_risk_snapshots",
            ["snapshot_month"],
        )
    if "ix_supplier_risk_snapshots_captured_by_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_risk_snapshots")}:
        op.create_index(
            "ix_supplier_risk_snapshots_captured_by_id",
            "supplier_risk_snapshots",
            ["captured_by_id"],
        )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("supplier_risk_snapshots"):
        op.drop_table("supplier_risk_snapshots")
