import pytest
from pydantic import ValidationError

from app.schemas.risk import RiskCreate, RiskUpdate


def test_risk_create_rejects_boolean_rating():
    with pytest.raises(ValidationError):
        RiskCreate(ref="RISK-001", title="Test risk", impact=True)


def test_risk_update_rejects_boolean_rating():
    with pytest.raises(ValidationError):
        RiskUpdate(likelihood=False)


def test_accepted_risk_requires_rationale():
    with pytest.raises(ValidationError):
        RiskCreate(ref="RISK-002", title="Accepted risk", status="Accepté")


def test_accepted_risk_with_rationale_is_valid():
    risk = RiskCreate(ref="RISK-003", title="Accepted risk", status="Accepté", treatment_plan="Decision approved by risk owner")
    assert risk.status == "Accepté"
