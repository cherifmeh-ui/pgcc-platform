"""Enforce risk score invariants and normalized reference uniqueness.

Revision ID: 0030_risk_integrity_constraints
Revises: 0029_supplier_access_link_scope
"""
from alembic import op
import sqlalchemy as sa

revision = "0030_risk_integrity_constraints"
down_revision = "0029_supplier_access_link_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    invalid_scores = bind.execute(sa.text("""
        SELECT count(*)
        FROM risks
        WHERE impact NOT BETWEEN 1 AND 5
           OR likelihood NOT BETWEEN 1 AND 5
           OR risk_level NOT BETWEEN 1 AND 25
           OR risk_level <> impact * likelihood
    """)).scalar_one()
    blank_refs = bind.execute(sa.text("""
        SELECT count(*) FROM risks WHERE btrim(ref) = ''
    """)).scalar_one()
    duplicate_refs = bind.execute(sa.text("""
        SELECT count(*) FROM (
            SELECT lower(btrim(ref))
            FROM risks
            GROUP BY lower(btrim(ref))
            HAVING count(*) > 1
        ) AS duplicates
    """)).scalar_one()
    if invalid_scores or blank_refs or duplicate_refs:
        raise RuntimeError(
            "Risk integrity migration blocked by historical data: "
            f"{invalid_scores} inconsistent score(s), {blank_refs} blank reference(s), "
            f"{duplicate_refs} case/space-normalized duplicate reference group(s). "
            "Reconcile these records before retrying; no automatic data rewrite is performed."
        )

    inspector = sa.inspect(bind)
    checks = {item["name"] for item in inspector.get_check_constraints("risks")}
    if "ck_risks_impact_range" not in checks:
        op.create_check_constraint(
            "ck_risks_impact_range", "risks", "impact BETWEEN 1 AND 5"
        )
    if "ck_risks_likelihood_range" not in checks:
        op.create_check_constraint(
            "ck_risks_likelihood_range", "risks", "likelihood BETWEEN 1 AND 5"
        )
    if "ck_risks_score_consistency" not in checks:
        op.create_check_constraint(
            "ck_risks_score_consistency",
            "risks",
            "risk_level BETWEEN 1 AND 25 AND risk_level = impact * likelihood",
        )
    if "ck_risks_ref_nonblank" not in checks:
        op.create_check_constraint(
            "ck_risks_ref_nonblank", "risks", "btrim(ref) <> ''"
        )

    indexes = {item["name"] for item in inspector.get_indexes("risks")}
    if "uq_risks_ref_ci" not in indexes:
        op.create_index(
            "uq_risks_ref_ci",
            "risks",
            [sa.text("lower(btrim(ref))")],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("risks")}
    if "uq_risks_ref_ci" in indexes:
        op.drop_index("uq_risks_ref_ci", table_name="risks")

    checks = {item["name"] for item in sa.inspect(bind).get_check_constraints("risks")}
    for name in (
        "ck_risks_ref_nonblank",
        "ck_risks_score_consistency",
        "ck_risks_likelihood_range",
        "ck_risks_impact_range",
    ):
        if name in checks:
            op.drop_constraint(name, "risks", type_="check")
