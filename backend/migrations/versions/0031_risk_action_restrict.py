"""Prevent deletion of risks from cascading into corrective action history.

Revision ID: 0031_risk_action_restrict
Revises: 0030_risk_integrity_constraints
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_risk_action_restrict"
down_revision = "0030_risk_integrity_constraints"
branch_labels = None
depends_on = None

_CONSTRAINT = "fk_action_items_risk_id_risks_restrict"


def _risk_foreign_keys(bind):
    return [
        item for item in sa.inspect(bind).get_foreign_keys("action_items")
        if item.get("referred_table") == "risks"
        and item.get("constrained_columns") == ["risk_id"]
    ]


def upgrade() -> None:
    bind = op.get_bind()
    foreign_keys = _risk_foreign_keys(bind)
    if (
        len(foreign_keys) == 1
        and foreign_keys[0].get("name") == _CONSTRAINT
        and (foreign_keys[0].get("options") or {}).get("ondelete", "").upper() == "RESTRICT"
    ):
        return

    for foreign_key in foreign_keys:
        name = foreign_key.get("name")
        if not name:
            raise RuntimeError(
                "Cannot safely replace the action_items.risk_id foreign key without its constraint name."
            )
        op.drop_constraint(name, "action_items", type_="foreignkey")

    op.create_foreign_key(
        _CONSTRAINT,
        "action_items",
        "risks",
        ["risk_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    bind = op.get_bind()
    for foreign_key in _risk_foreign_keys(bind):
        name = foreign_key.get("name")
        if not name:
            raise RuntimeError(
                "Cannot safely downgrade action_items.risk_id foreign key without its constraint name."
            )
        op.drop_constraint(name, "action_items", type_="foreignkey")

    op.create_foreign_key(
        "action_items_risk_id_fkey",
        "action_items",
        "risks",
        ["risk_id"],
        ["id"],
        ondelete="CASCADE",
    )
