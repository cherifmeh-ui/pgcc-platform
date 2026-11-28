"""Protect security audit logs against ordinary SQL mutation."""
from alembic import op
import sqlalchemy as sa

revision = "0023_security_logs_append_only"
down_revision = "0022_document_filename_unique"
branch_labels = None
depends_on = None

FUNCTION_NAME = "pgcc_prevent_security_log_mutation"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("security_logs"):
        return

    op.execute(sa.text(f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $pgcc$
        BEGIN
            RAISE EXCEPTION
                'security_logs is append-only; % is not permitted', TG_OP
                USING ERRCODE = '55000';
        END;
        $pgcc$;
    """))
    op.execute(sa.text("""
        DROP TRIGGER IF EXISTS trg_security_logs_no_update_delete
        ON security_logs
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_security_logs_no_update_delete
        BEFORE UPDATE OR DELETE ON security_logs
        FOR EACH ROW
        EXECUTE FUNCTION pgcc_prevent_security_log_mutation()
    """))
    op.execute(sa.text("""
        DROP TRIGGER IF EXISTS trg_security_logs_no_truncate
        ON security_logs
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_security_logs_no_truncate
        BEFORE TRUNCATE ON security_logs
        FOR EACH STATEMENT
        EXECUTE FUNCTION pgcc_prevent_security_log_mutation()
    """))


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("security_logs"):
        op.execute(sa.text("""
            DROP TRIGGER IF EXISTS trg_security_logs_no_update_delete
            ON security_logs
        """))
        op.execute(sa.text("""
            DROP TRIGGER IF EXISTS trg_security_logs_no_truncate
            ON security_logs
        """))
    op.execute(sa.text(
        "DROP FUNCTION IF EXISTS pgcc_prevent_security_log_mutation()"
    ))
