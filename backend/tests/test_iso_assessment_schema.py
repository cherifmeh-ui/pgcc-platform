from pydantic import ValidationError
import pytest

from app.api.v1.endpoints.compliance import AssessmentCreate


def test_assessment_requires_nonblank_justification():
    with pytest.raises(ValidationError):
        AssessmentCreate(
            applicability="Applicable",
            implementation_status="En cours",
            maturity_level=2,
            justification="   ",
        )


def test_assessment_rejects_invalid_applicability():
    with pytest.raises(ValidationError):
        AssessmentCreate(
            applicability="Maybe",
            implementation_status="En cours",
            maturity_level=2,
            justification="Evaluation documented",
        )


def test_assessment_rejects_boolean_maturity():
    with pytest.raises(ValidationError):
        AssessmentCreate(
            applicability="Applicable",
            implementation_status="En cours",
            maturity_level=True,
            justification="Evaluation documented",
        )


def test_assessment_rejects_out_of_range_maturity():
    with pytest.raises(ValidationError):
        AssessmentCreate(
            applicability="Applicable",
            implementation_status="En cours",
            maturity_level=6,
            justification="Evaluation documented",
        )


def test_assessment_normalizes_justification():
    payload = AssessmentCreate(
        applicability="Applicable",
        implementation_status="Implémenté",
        maturity_level=4,
        justification="  Control is implemented and verified.  ",
    )
    assert payload.justification == "Control is implemented and verified."
