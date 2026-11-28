"""Action plan lifecycle transition rules."""

from app.models.action_item import ActionStatus

_ALLOWED_TRANSITIONS: dict[ActionStatus, set[ActionStatus]] = {
    ActionStatus.TODO: {ActionStatus.IN_PROGRESS, ActionStatus.BLOCKED},
    ActionStatus.IN_PROGRESS: {ActionStatus.TODO, ActionStatus.BLOCKED, ActionStatus.DONE},
    ActionStatus.BLOCKED: {ActionStatus.TODO, ActionStatus.IN_PROGRESS},
    ActionStatus.DONE: set(),
}


def validate_action_transition(current: ActionStatus, target: ActionStatus) -> None:
    """Raise ValueError if a requested transition is not allowed."""
    if current == target:
        return
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Transition de statut interdite: {current.value} -> {target.value}")
