"""Initial schema baseline for PGCC.

This migration is intended for a fresh database. Existing deployments created by
SQLAlchemy create_all must be inspected and stamped only after verifying schema
equivalence; do not blindly run this migration against populated databases.
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The pgvector type must exist before metadata creates document_chunks.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # This baseline intentionally delegates table creation to SQLAlchemy metadata
    # so that model definitions remain the single schema source at this stage.
    from app.core.database import Base
    from app.models import action_item, application, document, document_chunk, entity_link, iso_control, iso_control_assessment, risk, security_log, user  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    raise NotImplementedError(
        "Initial baseline downgrade is intentionally disabled to prevent accidental data loss."
    )
