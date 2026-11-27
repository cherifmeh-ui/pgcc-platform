"""PostgreSQL integration tests for SQL-aggregated inventory quality metrics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.assets import get_asset_inventory_quality
from app.models.asset import Asset


DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_inventory_quality_sql_aggregates_active_assets_and_blank_values():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    marker = uuid4().hex[:12]
    asset_ids = [uuid4() for _ in range(4)]
    now = datetime.now(timezone.utc)
    try:
        async with sessions() as setup:
            setup.add_all([
                Asset(
                    id=asset_ids[0], reference=f"Q-PG-{marker}-1", name="Complete",
                    asset_type="hardware", lifecycle_status="Actif", criticality="Critique",
                    owner="Owner", classification="Confidentiel",
                    last_inventory_date=now, direction="DI",
                    end_of_support_date=now + timedelta(days=30),
                ),
                Asset(
                    id=asset_ids[1], reference=f"Q-PG-{marker}-2", name="Incomplete",
                    asset_type="hardware", lifecycle_status="Actif", criticality="Moyenne",
                    owner="   ", classification=None, last_inventory_date=None,
                    direction="", end_of_support_date=now - timedelta(days=1),
                ),
                Asset(
                    id=asset_ids[2], reference=f"Q-PG-{marker}-3", name="Partial",
                    asset_type="hardware", lifecycle_status="Actif", criticality="Faible",
                    owner=None, classification="Public", last_inventory_date=now,
                    direction="Ops", end_of_support_date=now + timedelta(days=100),
                ),
                Asset(
                    id=asset_ids[3], reference=f"Q-PG-{marker}-4", name="Retired",
                    asset_type="hardware", lifecycle_status="Retiré",
                    retired_at=now - timedelta(days=1), criticality="Moyenne",
                ),
            ])
            await setup.commit()

        async with sessions() as db:
            quality = await get_asset_inventory_quality(
                db=db, current_user=MagicMock(role="admin")
            )

        assert quality == {
            "total_active": 3,
            "missing_owner": 2,
            "missing_classification": 1,
            "missing_inventory_date": 1,
            "missing_criticality": 0,
            "missing_direction": 1,
            "support_overdue": 1,
            "support_ending_90_days": 1,
            "completeness_percent": 66.7,
        }
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Asset).where(Asset.id.in_(asset_ids)))
            await cleanup.commit()
        await engine.dispose()
