"""Persist audit events in an outbox before materializing immutable logs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_audit_outbox"
down_revision = "0023_security_logs_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("security_logs"):
        return

    columns = {column["name"] for column in inspector.get_columns("security_logs")}
    if "event_id" not in columns:
        op.add_column(
            "security_logs",
            sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    indexes = {index["name"] for index in inspector.get_indexes("security_logs")}
    if "uq_security_logs_event_id" not in indexes:
        op.create_index(
            "uq_security_logs_event_id",
            "security_logs",
            ["event_id"],
            unique=True,
            postgresql_where=sa.text("event_id IS NOT NULL"),
        )

    if not inspector.has_table("audit_outbox"):
        op.create_table(
            "audit_outbox",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
        )
    outbox_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("audit_outbox")}
    if "ix_audit_outbox_pending" not in outbox_indexes:
        op.create_index(
            "ix_audit_outbox_pending",
            "audit_outbox",
            ["created_at"],
            postgresql_where=sa.text("delivered_at IS NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("audit_outbox"):
        indexes = {index["name"] for index in inspector.get_indexes("audit_outbox")}
        if "ix_audit_outbox_pending" in indexes:
            op.drop_index("ix_audit_outbox_pending", table_name="audit_outbox")
        op.drop_table("audit_outbox")
    if inspector.has_table("security_logs"):
        indexes = {index["name"] for index in inspector.get_indexes("security_logs")}
        if "uq_security_logs_event_id" in indexes:
            op.drop_index("uq_security_logs_event_id", table_name="security_logs")
        columns = {column["name"] for column in inspector.get_columns("security_logs")}
        if "event_id" in columns:
            op.drop_column("security_logs", "event_id")
