"""Action-plan lifecycle validation for PGCC."""

from app.models.action_item import ActionStatus

ALLOWED_TRANSITIONS = {
    ActionStatus.TODO: {ActionStatus.IN_PROGRESS, ActionStatus.BLOCKED},
    ActionStatus.IN_PROGRESS: {ActionStatus.TODO, ActionStatus.BLOCKED, ActionStatus.DONE},
    ActionStatus.BLOCKED: {ActionStatus.TODO, ActionStatus.IN_PROGRESS},
    ActionStatus.DONE: set(),
}


def validate_action_transition(current: ActionStatus, target: ActionStatus) -> None:
    """Raise ValueError when an action status transition is not allowed."""
    if current == target:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Transition d'action non autorisée: {current.value} -> {target.value}")
