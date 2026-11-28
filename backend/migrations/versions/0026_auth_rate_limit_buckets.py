"""Add shared database-backed authentication rate-limit buckets."""
from alembic import op
import sqlalchemy as sa

revision = "0026_auth_rate_limit_buckets"
down_revision = "0025_user_auth_version"
branch_labels = None
depends_on = None


_TABLE = "auth_rate_limit_buckets"
_INDEX = "ix_auth_rate_limit_buckets_updated_at"
_CHECK = "ck_auth_rate_limit_buckets_attempts_nonnegative"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("bucket_key", sa.String(length=64), nullable=False),
            sa.Column("scope", sa.String(length=32), nullable=False),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("attempts >= 0", name=_CHECK),
            sa.PrimaryKeyConstraint("bucket_key"),
        )
        inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    required_columns = {
        "bucket_key",
        "scope",
        "window_started_at",
        "attempts",
        "blocked_until",
        "updated_at",
    }
    missing_columns = required_columns - columns
    if missing_columns:
        raise RuntimeError(
            f"{_TABLE} exists but is missing required columns: {sorted(missing_columns)}"
        )

    checks = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints(_TABLE)
    }
    if _CHECK not in checks:
        op.create_check_constraint(_CHECK, _TABLE, "attempts >= 0")

    indexes = {index["name"] for index in inspector.get_indexes(_TABLE)}
    if _INDEX not in indexes:
        op.create_index(_INDEX, _TABLE, ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    indexes = {index["name"] for index in inspector.get_indexes(_TABLE)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
