"""Add document ownership and department scope for row-level ACL."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0028_document_acl"
down_revision = "0027_document_file_sha256"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("documents") or not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "owner_id" not in columns:
        op.add_column(
            "documents",
            sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "department" not in columns:
        op.add_column(
            "documents",
            sa.Column("department", sa.String(length=255), nullable=True),
        )

    inspector = sa.inspect(bind)
    foreign_keys = inspector.get_foreign_keys("documents")
    if not any(
        fk.get("constrained_columns") == ["owner_id"]
        and fk.get("referred_table") == "users"
        for fk in foreign_keys
    ):
        op.create_foreign_key(
            "fk_documents_owner_id_users",
            "documents",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("documents")}
    if "ix_documents_owner_id" not in indexes:
        op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    if "ix_documents_department" not in indexes:
        op.create_index("ix_documents_department", "documents", ["department"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("documents"):
        return

    foreign_keys = inspector.get_foreign_keys("documents")
    if any(fk.get("name") == "fk_documents_owner_id_users" for fk in foreign_keys):
        op.drop_constraint("fk_documents_owner_id_users", "documents", type_="foreignkey")

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("documents")}
    if "ix_documents_owner_id" in indexes:
        op.drop_index("ix_documents_owner_id", table_name="documents")
    if "ix_documents_department" in indexes:
        op.drop_index("ix_documents_department", table_name="documents")

    columns = {column["name"] for column in sa.inspect(bind).get_columns("documents")}
    if "department" in columns:
        op.drop_column("documents", "department")
    if "owner_id" in columns:
        op.drop_column("documents", "owner_id")
