"""Add versioned supplier security assessments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_supplier_assessments"
down_revision = "0013_supplier_contracts"
branch_labels = None
depends_on = None

def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("supplier_assessments"):
        op.create_table(
            "supplier_assessments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("assessment_type", sa.String(30), nullable=False, server_default="Initiale"),
            sa.Column("scope", sa.Text(), nullable=False),
            sa.Column("questionnaire_version", sa.String(50), nullable=False),
            sa.Column("questionnaire_snapshot", postgresql.JSONB(), nullable=False),
            sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("status", sa.String(20), nullable=False, server_default="Brouillon"),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
            sa.Column("risk_level", sa.String(20), nullable=True),
            sa.Column("decision", sa.String(30), nullable=True),
            sa.Column("assessed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("validated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("next_review_at", sa.Date(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("assessment_type IN ('Initiale', 'Périodique', 'Renouvellement', 'Incident', 'Changement majeur')", name="ck_supplier_assessments_type"),
            sa.CheckConstraint("status IN ('Brouillon', 'À valider', 'Validée', 'Clôturée')", name="ck_supplier_assessments_status"),
            sa.CheckConstraint("risk_level IS NULL OR risk_level IN ('Faible', 'Moyen', 'Élevé', 'Critique')", name="ck_supplier_assessments_risk"),
            sa.CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_supplier_assessments_score"),
            sa.CheckConstraint("(status = 'Brouillon' AND submitted_at IS NULL AND validated_at IS NULL) OR (status = 'À valider' AND submitted_at IS NOT NULL AND validated_at IS NULL) OR (status IN ('Validée', 'Clôturée') AND submitted_at IS NOT NULL AND validated_at IS NOT NULL)", name="ck_supplier_assessments_lifecycle"),
        )
    if "ix_supplier_assessments_supplier_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_assessments")}:
        op.create_index("ix_supplier_assessments_supplier_id", "supplier_assessments", ["supplier_id"])
    if "ix_supplier_assessments_assessed_by_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_assessments")}:
        op.create_index("ix_supplier_assessments_assessed_by_id", "supplier_assessments", ["assessed_by_id"])
    if "ix_supplier_assessments_validated_by_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_assessments")}:
        op.create_index("ix_supplier_assessments_validated_by_id", "supplier_assessments", ["validated_by_id"])
    if "ix_supplier_assessments_supplier_status" not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("supplier_assessments")}:
        op.create_index("ix_supplier_assessments_supplier_status", "supplier_assessments", ["supplier_id", "status", "created_at"])

def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("supplier_assessments"):
        op.drop_table("supplier_assessments")