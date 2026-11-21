from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.actions import ActionCreate, ActionUpdate, create_action, update_action
from app.models.action_item import ActionStatus


@pytest.mark.asyncio
async def test_create_action_rejects_unknown_assignee():
    db = AsyncMock()
    risk_result = MagicMock()
    risk_result.scalar_one_or_none.return_value = MagicMock()
    assignee_result = MagicMock()
    assignee_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [risk_result, assignee_result]

    data = ActionCreate(
        risk_id="00000000-0000-0000-0000-000000000001",
        title="Test action",
        assigned_to="unknown@example.com",
    )

    with pytest.raises(HTTPException) as exc:
        await create_action(data, MagicMock(), db, MagicMock())

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_action_rejects_unknown_assignee():
    db = AsyncMock()
    action = MagicMock()
    action.status = ActionStatus.TODO
    action.description = None
    action_result = MagicMock()
    action_result.scalar_one_or_none.return_value = action
    assignee_result = MagicMock()
    assignee_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [action_result, assignee_result]

    with pytest.raises(HTTPException) as exc:
        await update_action(
            action_id="00000000-0000-0000-0000-000000000001",
            data=ActionUpdate(assigned_to="unknown@example.com"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
        )

    assert exc.value.status_code == 400
