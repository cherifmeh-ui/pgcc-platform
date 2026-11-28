"""PostgreSQL integration tests for SQL-aggregated inventory quality metrics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import csv
import io
import os
from unittest.mock import AsyncMock, MagicMock
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


@pytest.mark.asyncio
async def test_asset_inventory_pagination_matches_filtered_csv_export_over_http(monkeypatch):
    """Page traversal and CSV export must expose the same filtered inventory."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import assets as assets_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.models.user import User

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-inventory-pagination-jwt-secret-long"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    audit = AsyncMock()
    monkeypatch.setattr(assets_endpoint, "log_action", audit)

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor_email = f"phase0-inventory-page-{actor_id.hex}@example.invalid"
    actor = User(
        id=actor_id,
        email=actor_email,
        full_name="Phase 0 inventory auditor",
        role="auditor",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=False,
        auth_version=5,
    )
    now = datetime.now(timezone.utc)
    matching_assets = [
        Asset(
            reference=f"INV-{actor_id.hex[:8]}-{suffix}",
            name=f"{name} inventory",
            asset_type="hardware",
            lifecycle_status="Actif",
            criticality="Critique",
            owner="Alice Operations",
            direction="DI",
            location="Tunis Datacenter",
            classification="Confidentiel",
        )
        for suffix, name in (("A", "Alpha"), ("B", "Beta"), ("C", "Gamma"))
    ]
    nonmatching_assets = [
        Asset(
            reference=f"INV-{actor_id.hex[:8]}-SOFT",
            name="Delta inventory",
            asset_type="software",
            lifecycle_status="Actif",
            criticality="Critique",
            owner="Alice Operations",
            direction="DI",
            location="Tunis Datacenter",
            classification="Confidentiel",
        ),
        Asset(
            reference=f"INV-{actor_id.hex[:8]}-RETIRED",
            name="Epsilon inventory",
            asset_type="hardware",
            lifecycle_status="Retiré",
            retired_at=now,
            criticality="Critique",
            owner="Alice Operations",
            direction="DI",
            location="Tunis Datacenter",
            classification="Confidentiel",
        ),
    ]
    all_assets = matching_assets + nonmatching_assets
    asset_ids = []
    try:
        async with sessions() as setup:
            setup.add(actor)
            setup.add_all(all_assets)
            await setup.commit()
            for asset in all_assets:
                await setup.refresh(asset)
                asset_ids.append(asset.id)

        app = FastAPI()
        app.include_router(assets_endpoint.router, prefix="/api/v1")

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        token = create_access_token(
            subject=actor_email, role="auditor", auth_version=5
        )
        headers = {"Authorization": f"Bearer {token}"}
        filters = {
            "q": "INV",
            "asset_type": "hardware",
            "criticality": "Critique",
            "direction": "DI",
            "owner": "Alice",
            "classification": "Confidentiel",
            "location": "Tunis",
            "page_size": 2,
        }

        with TestClient(app) as client:
            first_page = client.get(
                "/api/v1/assets/page",
                params={**filters, "page": 1},
                headers=headers,
            )
            second_page = client.get(
                "/api/v1/assets/page",
                params={**filters, "page": 2},
                headers=headers,
            )
            exported = client.get(
                "/api/v1/assets/export.csv",
                params={key: value for key, value in filters.items() if key != "page_size"},
                headers=headers,
            )

        assert first_page.status_code == 200, first_page.text
        assert second_page.status_code == 200, second_page.text
        assert exported.status_code == 200, exported.text
        first_json, second_json = first_page.json(), second_page.json()
        assert first_json["total"] == second_json["total"] == 3
        assert first_json["pages"] == second_json["pages"] == 2
        assert first_json["page"] == 1 and second_json["page"] == 2
        assert len(first_json["items"]) == 2
        assert len(second_json["items"]) == 1

        paginated_references = [
            item["reference"]
            for item in first_json["items"] + second_json["items"]
        ]
        csv_rows = list(
            csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))
        )
        exported_references = [row["reference"] for row in csv_rows]
        expected_references = [
            asset.reference for asset in sorted(matching_assets, key=lambda item: item.name)
        ]
        assert paginated_references == expected_references
        assert exported_references == expected_references
        audit.assert_awaited_once()
        assert audit.await_args.kwargs["action"] == "EXPORT"
    finally:
        async with sessions() as cleanup:
            if asset_ids:
                await cleanup.execute(delete(Asset).where(Asset.id.in_(asset_ids)))
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()
