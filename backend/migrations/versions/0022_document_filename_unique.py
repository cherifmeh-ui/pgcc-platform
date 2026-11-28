"""Enforce case-insensitive uniqueness for uploaded document filenames."""
from alembic import op
import sqlalchemy as sa

revision = "0022_document_filename_unique"
down_revision = "0021_refresh_token_sessions"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_documents_filename_ci"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("documents"):
        return

    duplicates = bind.execute(sa.text("""
        SELECT lower(btrim(filename)) AS normalized_filename
        FROM documents
        WHERE filename IS NOT NULL AND btrim(filename) <> ''
        GROUP BY lower(btrim(filename))
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError(
            "Cannot create uq_documents_filename_ci: duplicate document filenames "
            f"exist for normalized filename {duplicates[0]!r}. Resolve duplicates "
            "before retrying this migration."
        )

    indexes = {item["name"] for item in inspector.get_indexes("documents")}
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "documents",
            [sa.text("lower(btrim(filename))")],
            unique=True,
            postgresql_where=sa.text(
                "filename IS NOT NULL AND btrim(filename) <> ''"
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("documents"):
        indexes = {item["name"] for item in inspector.get_indexes("documents")}
        if INDEX_NAME in indexes:
            op.drop_index(INDEX_NAME, table_name="documents")
