from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.assets import get_asset_inventory_quality


@pytest.mark.asyncio
async def test_inventory_quality_counts_missing_fields_and_support_dates():
    now = datetime.now(timezone.utc)
    complete = MagicMock(
        owner="Owner", classification="Confidential", last_inventory_date=now,
        criticality="Critique", direction="DI", end_of_support_date=now + timedelta(days=30),
        retired_at=None,
    )
    incomplete = MagicMock(
        owner=None, classification="", last_inventory_date=None,
        criticality="Moyenne", direction="", end_of_support_date=now - timedelta(days=1),
        retired_at=None,
    )
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [complete, incomplete]
    db.execute.return_value = result

    quality = await get_asset_inventory_quality(db=db, current_user=MagicMock(role="admin"))

    assert quality["total_active"] == 2
    assert quality["missing_owner"] == 1
    assert quality["missing_classification"] == 1
    assert quality["missing_inventory_date"] == 1
    assert quality["missing_criticality"] == 0
    assert quality["missing_direction"] == 1
    assert quality["support_overdue"] == 1
    assert quality["support_ending_90_days"] == 1
    assert quality["completeness_percent"] == 60.0


@pytest.mark.asyncio
async def test_inventory_quality_empty_inventory_is_complete():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    quality = await get_asset_inventory_quality(db=db, current_user=MagicMock(role="admin"))

    assert quality["total_active"] == 0
    assert quality["completeness_percent"] == 100.0
