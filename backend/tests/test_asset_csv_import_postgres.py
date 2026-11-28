"""PostgreSQL-backed HTTP tests for CSV asset import atomicity and concurrency."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.asset import Asset
from app.models.audit_outbox import AuditOutbox
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_asset_csv_concurrent_http_import_is_atomic_with_real_postgres(monkeypatch):
    """Force two HTTP imports past preview together and verify DB uniqueness is atomic."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import assets as assets_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-postgres-csv-race-jwt-secret-long-enough"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor_email = f"phase0-csv-race-{actor_id.hex}@example.invalid"
    actor = User(
        id=actor_id,
        email=actor_email,
        full_name="Phase 0 CSV concurrency administrator",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=2,
    )
    reference = f"PH0-RACE-{actor_id.hex[:12]}"
    filename = f"phase0-concurrency-{actor_id.hex}.csv"
    csv_content = (
        "reference,name,asset_type\n"
        f"{reference},Concurrent CSV asset,hardware\n"
    )
    barrier = Barrier(2)
    original_preview = assets_endpoint.preview_asset_csv_import

    async def synchronized_preview(*args, **kwargs):
        preview = await original_preview(*args, **kwargs)
        barrier.wait(timeout=20)
        return preview

    monkeypatch.setattr(
        assets_endpoint, "preview_asset_csv_import", synchronized_preview
    )

    try:
        async with sessions() as setup:
            setup.add(actor)
            await setup.commit()

        app = FastAPI()
        app.include_router(assets_endpoint.router, prefix="/api/v1")

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        token = create_access_token(
            subject=actor_email, role="admin", auth_version=2
        )
        headers = {"Authorization": f"Bearer {token}"}

        def send_import():
            with TestClient(app) as client:
                return client.post(
                    "/api/v1/assets/import/confirm",
                    headers=headers,
                    files={"file": (filename, csv_content, "text/csv")},
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: send_import(), range(2)))

        assert sorted(response.status_code for response in responses) == [201, 409]
        success = next(response for response in responses if response.status_code == 201)
        conflict = next(response for response in responses if response.status_code == 409)
        assert success.json()["imported"] == 1
        assert "Aucun actif n'a été importé" in conflict.json()["detail"]

        async with sessions() as verify:
            persisted_assets = (
                await verify.execute(
                    select(Asset).where(Asset.reference == reference)
                )
            ).scalars().all()
            assert len(persisted_assets) == 1
            import_events = (
                await verify.execute(
                    select(AuditOutbox.id).where(
                        AuditOutbox.payload["action"].astext == "IMPORT",
                        AuditOutbox.payload["details"].astext
                        == f"CSV asset import completed: 1 assets from {filename}",
                    )
                )
            ).scalars().all()
            assert len(import_events) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Asset).where(Asset.reference == reference))
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["details"].astext
                    == f"CSV asset import completed: 1 assets from {filename}"
                )
            )
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()



@pytest.mark.asyncio
async def test_asset_csv_multirow_conflict_rolls_back_every_insert(monkeypatch):
    """A concurrent uniqueness conflict on row two must roll back row one too."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import assets as assets_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-postgres-csv-atomic-jwt-secret-long"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor_email = f"phase0-csv-atomic-{actor_id.hex}@example.invalid"
    actor = User(
        id=actor_id,
        email=actor_email,
        full_name="Phase 0 CSV atomicity administrator",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=3,
    )
    first_reference = f"PH0-ATOMIC-A-{actor_id.hex[:10]}"
    conflict_reference = f"PH0-ATOMIC-B-{actor_id.hex[:10]}"
    filename = f"phase0-atomic-{actor_id.hex}.csv"
    csv_content = (
        "reference,name,asset_type\n"
        f"{first_reference},First batch row,hardware\n"
        f"{conflict_reference},Second batch row,hardware\n"
    )
    original_preview = assets_endpoint.preview_asset_csv_import

    async def inject_competing_insert(*args, **kwargs):
        preview = await original_preview(*args, **kwargs)
        async with sessions() as competing:
            competing.add(
                Asset(
                    reference=conflict_reference,
                    name="Competing transaction asset",
                    asset_type="hardware",
                    lifecycle_status="Identifié",
                    criticality="Moyenne",
                )
            )
            await competing.commit()
        return preview

    monkeypatch.setattr(
        assets_endpoint, "preview_asset_csv_import", inject_competing_insert
    )

    try:
        async with sessions() as setup:
            setup.add(actor)
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

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/assets/import/confirm",
                headers=headers,
                files={"file": (filename, csv_content, "text/csv")},
            )

        assert response.status_code == 409, response.text
        assert "Aucun actif n'a été importé" in response.json()["detail"]

        async with sessions() as verify:
            first_row = (
                await verify.execute(
                    select(Asset).where(Asset.reference == first_reference)
                )
            ).scalar_one_or_none()
            competing_row = (
                await verify.execute(
                    select(Asset).where(Asset.reference == conflict_reference)
                )
            ).scalar_one()
            import_events = (
                await verify.execute(
                    select(AuditOutbox.id).where(
                        AuditOutbox.payload["action"].astext == "IMPORT",
                        AuditOutbox.payload["details"].astext
                        == f"CSV asset import completed: 2 assets from {filename}",
                    )
                )
            ).scalars().all()
            assert first_row is None
            assert competing_row.name == "Competing transaction asset"
            assert import_events == []
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(Asset).where(
                    Asset.reference.in_([first_reference, conflict_reference])
                )
            )
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["details"].astext
                    == f"CSV asset import completed: 2 assets from {filename}"
                )
            )
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_csv_http_preview_then_confirm_persists_same_validated_data(monkeypatch):
    """Exercise preview and confirm over HTTP with the same CSV and real PostgreSQL."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import assets as assets_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-postgres-csv-preview-confirm-secret-long"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor_email = f"phase0-csv-preview-confirm-{actor_id.hex}@example.invalid"
    actor = User(
        id=actor_id,
        email=actor_email,
        full_name="Phase 0 CSV preview-confirm administrator",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=4,
    )
    reference = f"PH0-PREVIEW-CONFIRM-{actor_id.hex[:10]}"
    filename = f"phase0-preview-confirm-{actor_id.hex}.csv"
    csv_content = (
        "reference,name,asset_type,criticality,owner,comment\\n"
        f'{reference},"Serveur, production",hardware,Critique,Direction IT,"ligne 1; ligne 2"\\n'
    )
    app = FastAPI()
    app.include_router(assets_endpoint.router, prefix="/api/v1")

    async def override_db():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    token = create_access_token(
        subject=actor_email, role="admin", auth_version=4
    )
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with sessions() as setup:
            setup.add(actor)
            await setup.commit()

        with TestClient(app) as client:
            preview_response = client.post(
                "/api/v1/assets/import/preview",
                headers=headers,
                files={
                    "file": (
                        filename,
                        csv_content.encode("utf-8"),
                        "text/csv",
                    )
                },
            )
            assert preview_response.status_code == 200, preview_response.text
            preview = preview_response.json()
            assert preview["can_import"] is True
            assert preview["rows_parsed"] == 1
            assert preview["rows_valid"] == 1
            assert preview["validated_rows"][0]["data"]["reference"] == reference
            assert preview["validated_rows"][0]["data"]["name"] == "Serveur, production"
            assert preview["validated_rows"][0]["data"]["comment"] == "ligne 1; ligne 2"

            confirm_response = client.post(
                "/api/v1/assets/import/confirm",
                headers=headers,
                files={
                    "file": (
                        filename,
                        csv_content.encode("utf-8"),
                        "text/csv",
                    )
                },
            )
            assert confirm_response.status_code == 201, confirm_response.text
            assert confirm_response.json()["imported"] == 1

        async with sessions() as verify:
            persisted = (
                await verify.execute(
                    select(Asset).where(Asset.reference == reference)
                )
            ).scalar_one()
            assert persisted.name == preview["validated_rows"][0]["data"]["name"]
            assert persisted.asset_type == preview["validated_rows"][0]["data"]["asset_type"]
            assert persisted.criticality == preview["validated_rows"][0]["data"]["criticality"]
            assert persisted.owner == preview["validated_rows"][0]["data"]["owner"]
            assert persisted.comment == preview["validated_rows"][0]["data"]["comment"]

            import_events = (
                await verify.execute(
                    select(AuditOutbox.id).where(
                        AuditOutbox.payload["action"].astext == "IMPORT",
                        AuditOutbox.payload["details"].astext
                        == f"CSV asset import completed: 1 assets from {filename}",
                    )
                )
            ).scalars().all()
            assert len(import_events) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Asset).where(Asset.reference == reference))
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["details"].astext
                    == f"CSV asset import completed: 1 assets from {filename}"
                )
            )
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()
