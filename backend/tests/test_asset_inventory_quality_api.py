from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.assets import _csv_safe_value, get_asset_inventory_quality


@pytest.mark.parametrize(
    "value",
    [
        "=HYPERLINK(\"https://example.invalid\")",
        "+1+1",
        "-1+1",
        "@SUM(A1:A2)",
        "  =1+1",
        "\t=1+1",
        "\r=1+1",
        "\n=1+1",
        "\ufeff=1+1",
    ],
)
def test_csv_export_neutralizes_formula_markers_after_leading_whitespace(value):
    assert _csv_safe_value(value) == "'" + value


def test_csv_export_preserves_ordinary_text_and_empty_values():
    assert _csv_safe_value("PGCC asset inventory") == "PGCC asset inventory"
    assert _csv_safe_value(None) == ""


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
    result.one.return_value = (2, 1, 1, 1, 0, 1, 1, 1)
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
    result.one.return_value = (0, 0, 0, 0, 0, 0, 0, 0)
    db.execute.return_value = result

    quality = await get_asset_inventory_quality(db=db, current_user=MagicMock(role="admin"))

    assert quality["total_active"] == 0
    assert quality["completeness_percent"] == 100.0


@pytest.mark.asyncio
async def test_inventory_quality_uses_single_database_aggregate_query():
    db = AsyncMock()
    result = MagicMock()
    result.one.return_value = (4, 1, 0, 2, 0, 1, 1, 2)
    db.execute.return_value = result

    quality = await get_asset_inventory_quality(db=db, current_user=MagicMock(role="admin"))

    statement = str(db.execute.await_args.args[0]).lower()
    assert "count(assets.id)" in statement
    assert "sum(case when" in statement
    assert "retired_at is null" in statement
    assert quality["total_active"] == 4
    assert quality["missing_owner"] == 1
    assert quality["support_overdue"] == 1
    assert quality["support_ending_90_days"] == 2
