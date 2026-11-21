import pytest

from app.models.action_item import ActionStatus
from app.services.action_lifecycle import validate_action_transition


@pytest.mark.parametrize(
    "current,target",
    [
        (ActionStatus.TODO, ActionStatus.IN_PROGRESS),
        (ActionStatus.TODO, ActionStatus.BLOCKED),
        (ActionStatus.IN_PROGRESS, ActionStatus.DONE),
        (ActionStatus.IN_PROGRESS, ActionStatus.BLOCKED),
        (ActionStatus.BLOCKED, ActionStatus.IN_PROGRESS),
        (ActionStatus.BLOCKED, ActionStatus.TODO),
        (ActionStatus.IN_PROGRESS, ActionStatus.TODO),
    ],
)
def test_allowed_action_transitions(current, target):
    validate_action_transition(current, target)


@pytest.mark.parametrize(
    "current,target",
    [
        (ActionStatus.TODO, ActionStatus.DONE),
        (ActionStatus.BLOCKED, ActionStatus.DONE),
        (ActionStatus.DONE, ActionStatus.TODO),
        (ActionStatus.DONE, ActionStatus.IN_PROGRESS),
        (ActionStatus.DONE, ActionStatus.BLOCKED),
    ],
)
def test_forbidden_action_transitions(current, target):
    with pytest.raises(ValueError):
        validate_action_transition(current, target)


def test_same_status_transition_is_idempotent():
    validate_action_transition(ActionStatus.IN_PROGRESS, ActionStatus.IN_PROGRESS)
