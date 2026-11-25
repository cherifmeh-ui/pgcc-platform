"""Persist and backfill SHA-256 for original document binaries."""
from __future__ import annotations

import hashlib

from alembic import op
import sqlalchemy as sa

revision = "0027_document_file_sha256"
down_revision = "0026_auth_rate_limit_buckets"
branch_labels = None
depends_on = None

_TABLE = "documents"
_COLUMN = "file_sha256"
_BATCH_SIZE = 100


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return

    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    if _COLUMN not in columns:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=64), nullable=True))

    # Backfill existing binaries in bounded batches. A nullable digest is retained
    # only for legacy rows without an original binary.
    metadata = sa.MetaData()
    documents = sa.Table(_TABLE, metadata, autoload_with=bind)
    last_id = None
    while True:
        query = (
            sa.select(documents.c.id, documents.c.file_data)
            .where(
                documents.c.file_data.is_not(None),
                documents.c.file_sha256.is_(None),
            )
            .order_by(documents.c.id)
            .limit(_BATCH_SIZE)
        )
        if last_id is not None:
            query = query.where(documents.c.id > last_id)
        rows = bind.execute(query).fetchall()
        if not rows:
            break
        for row in rows:
            digest = hashlib.sha256(bytes(row.file_data)).hexdigest()
            bind.execute(
                sa.update(documents)
                .where(documents.c.id == row.id)
                .values(file_sha256=digest)
            )
        last_id = rows[-1].id

    # Refuse to silently leave any binary without a matching-format digest.
    invalid = bind.execute(
        sa.select(sa.func.count())
        .select_from(documents)
        .where(
            documents.c.file_data.is_not(None),
            sa.or_(
                documents.c.file_sha256.is_(None),
                sa.func.length(documents.c.file_sha256) != 64,
            ),
        )
    ).scalar_one()
    if invalid:
        raise RuntimeError(
            f"{invalid} document binaries have no valid SHA-256 after backfill."
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE):
        columns = {column["name"] for column in inspector.get_columns(_TABLE)}
        if _COLUMN in columns:
            op.drop_column(_TABLE, _COLUMN)
