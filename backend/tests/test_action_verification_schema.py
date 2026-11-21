import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.actions import ActionVerificationCreate


@pytest.mark.parametrize("outcome", ["Effective", "Ineffective", "Follow-up required"])
def test_action_verification_accepts_supported_outcomes(outcome):
    payload = ActionVerificationCreate(outcome=outcome, notes="Review performed.")
    assert payload.outcome == outcome


def test_action_verification_rejects_unknown_outcome():
    with pytest.raises(ValidationError):
        ActionVerificationCreate(outcome="Passed", notes="Review performed.")


def test_action_verification_requires_nonblank_notes():
    with pytest.raises(ValidationError):
        ActionVerificationCreate(outcome="Effective", notes="   ")
