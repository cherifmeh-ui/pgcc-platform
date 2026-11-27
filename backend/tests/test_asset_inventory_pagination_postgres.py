"""PostgreSQL-backed API integration tests for asset inventory pagination/export."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.asset import Asset
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)
@pytest.mark.asyncio
async def test_asset_inventory_pagination_and_csv_export_use_identical_postgres_filters(
    monkeypatch,
):
    """Prove paginated HTTP results and CSV export share filter/order semantics."""
    import csv
    import io

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import assets as assets_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-inventory-pagination-jwt-secret-long-enough"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(assets_endpoint, "log_action", AsyncMock())

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor_email = f"phase0-inventory-{actor_id.hex}@example.invalid"
    actor = User(
        id=actor_id,
        email=actor_email,
        full_name="Phase 0 inventory export administrator",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=3,
    )
    marker = actor_id.hex[:12]
    assets = [
        Asset(
            reference=f"PH0-PAGE-{marker}-A",
            name="Phase0 Pagination A - application server",
            asset_type="hardware",
            owner="RSSI",
            direction="DI",
            lifecycle_status="Actif",
        ),
        Asset(
            reference=f"PH0-PAGE-{marker}-B",
            name="Phase0 Pagination B - database server",
            asset_type="hardware",
            owner="RSSI",
            direction="DI",
            lifecycle_status="Actif",
        ),
        Asset(
            reference=f"PH0-PAGE-{marker}-C",
            name="Phase0 Pagination C - backup server",
            asset_type="hardware",
            owner="RSSI",
            direction="DI",
            lifecycle_status="Actif",
        ),
        Asset(
            reference=f"PH0-PAGE-{marker}-X",
            name="Phase0 Pagination excluded asset",
            asset_type="hardware",
            owner="Exploitation",
            direction="RH",
            lifecycle_status="Actif",
        ),
    ]
    try:
        async with sessions() as setup:
            setup.add(actor)
            setup.add_all(assets)
            await setup.commit()

        app = FastAPI()
        app.include_router(assets_endpoint.router, prefix="/api/v1")

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        token = create_access_token(
            subject=actor_email, role="admin", auth_version=3
        )
        headers = {"Authorization": f"Bearer {token}"}
        filters = {
            "q": "Phase0 Pagination",
            "asset_type": "hardware",
            "direction": "DI",
            "owner": "RSSI",
            "include_retired": "false",
        }

        with TestClient(app) as client:
            first_page = client.get(
                "/api/v1/assets/page",
                params={**filters, "page": 1, "page_size": 2},
                headers=headers,
            )
            second_page = client.get(
                "/api/v1/assets/page",
                params={**filters, "page": 2, "page_size": 2},
                headers=headers,
            )
            exported = client.get(
                "/api/v1/assets/export.csv",
                params=filters,
                headers=headers,
            )

        assert first_page.status_code == 200, first_page.text
        assert second_page.status_code == 200, second_page.text
        assert exported.status_code == 200, exported.text
        first_payload = first_page.json()
        second_payload = second_page.json()
        assert first_payload["total"] == 3
        assert first_payload["pages"] == 2
        assert first_payload["page"] == 1
        assert second_payload["page"] == 2
        assert len(first_payload["items"]) == 2
        assert len(second_payload["items"]) == 1

        paginated_references = [
            item["reference"]
            for item in first_payload["items"] + second_payload["items"]
        ]
        csv_rows = list(
            csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig")))
        )
        exported_references = [row["reference"] for row in csv_rows]

        assert exported_references == paginated_references
        assert set(exported_references) == {asset.reference for asset in assets[:3]}
        assert all(row["direction"] == "DI" for row in csv_rows)
        assert all(row["owner"] == "RSSI" for row in csv_rows)
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(Asset).where(Asset.reference.in_(
                    [asset.reference for asset in assets]
                ))
            )
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()
