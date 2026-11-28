from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.actions import verify_action_effectiveness, ActionVerificationCreate
from app.models.action_item import ActionStatus


@pytest.mark.asyncio
async def test_effectiveness_verification_rejected_before_action_completion():
    db = AsyncMock()
    result = MagicMock()
    action = MagicMock()
    action.status = ActionStatus.IN_PROGRESS
    result.scalar_one_or_none.return_value = action
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await verify_action_effectiveness(
            action_id=UUID("00000000-0000-0000-0000-000000000001"),
            data=ActionVerificationCreate(outcome="Effective", notes="Test"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(),
        )

    assert exc.value.status_code == 409
    db.commit.assert_not_awaited()
