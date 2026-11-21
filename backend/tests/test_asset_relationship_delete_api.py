from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.assets import delete_asset_relationship


ASSET_ID = UUID("00000000-0000-0000-0000-000000000001")
RELATION_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_delete_relationship_returns_404_when_not_attached_to_asset():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await delete_asset_relationship(
            asset_id=ASSET_ID,
            relationship_id=RELATION_ID,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="user@example.test"),
        )
    assert exc.value.status_code == 404
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_relationship_removes_only_relationship_linked_to_asset(monkeypatch):
    db = AsyncMock()
    relationship = MagicMock(
        id=RELATION_ID,
        source_asset_id=ASSET_ID,
        target_asset_id=UUID("00000000-0000-0000-0000-000000000003"),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = relationship
    db.execute.return_value = result
    log_mock = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.log_action", log_mock)

    await delete_asset_relationship(
        asset_id=ASSET_ID,
        relationship_id=RELATION_ID,
        request=MagicMock(),
        db=db,
        current_user=MagicMock(email="user@example.test"),
    )

    db.delete.assert_awaited_once_with(relationship)
    db.commit.assert_awaited_once()
    log_mock.assert_awaited_once()
