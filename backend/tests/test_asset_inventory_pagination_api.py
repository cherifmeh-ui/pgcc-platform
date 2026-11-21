from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.assets import list_assets_page


@pytest.mark.asyncio
async def test_asset_inventory_page_returns_total_and_page_metadata():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 31
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = ["asset-1", "asset-2"]
    db.execute.side_effect = [count_result, item_result]

    response = await list_assets_page(
        q="serveur",
        asset_type="hardware",
        criticality=None,
        lifecycle_status=None,
        direction="DI",
        owner="admin",
        classification=None,
        location=None,
        include_retired=False,
        page=2,
        page_size=10,
        db=db,
        current_user=MagicMock(role="admin"),
    )

    assert response["items"] == ["asset-1", "asset-2"]
    assert response["total"] == 31
    assert response["page"] == 2
    assert response["page_size"] == 10
    assert response["pages"] == 4
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_asset_inventory_page_returns_zero_pages_for_empty_inventory():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [count_result, item_result]

    response = await list_assets_page(
        q=None, asset_type=None, criticality=None, lifecycle_status=None,
        direction=None, owner=None, classification=None, location=None,
        include_retired=False, page=1, page_size=25, db=db,
        current_user=MagicMock(role="admin"),
    )

    assert response["items"] == []
    assert response["total"] == 0
    assert response["pages"] == 0
