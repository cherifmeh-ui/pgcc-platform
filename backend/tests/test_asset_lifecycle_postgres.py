"""PostgreSQL transaction tests for asset retirement and audit consistency."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.assets import retire_asset
from app.models.asset import Asset
from app.models.audit_outbox import AuditOutbox
from app.models.supplier import Supplier, SupplierAccessRequest, SupplierAssetLink
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "DELETE",
        "path": "/api/v1/assets/phase0-retirement-test",
        "headers": [(b"user-agent", b"phase0-asset-retirement-test")],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 80),
        "scheme": "http",
        "query_string": b"",
    })


async def _cleanup(sessions, asset_id):
    async with sessions() as db:
        await db.execute(
            delete(AuditOutbox).where(
                AuditOutbox.payload["resource_id"].astext == str(asset_id)
            )
        )
        await db.execute(delete(Asset).where(Asset.id == asset_id))
        await db.commit()


@pytest.mark.asyncio
async def test_asset_retirement_and_audit_event_commit_together():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_id = uuid4()
    try:
        async with sessions() as setup:
            setup.add(Asset(
                id=asset_id,
                reference=f"PHASE0-RETIRE-{asset_id.hex[:12]}",
                name="Phase 0 retirement transaction",
                asset_type="hardware",
                lifecycle_status="Actif",
                retired_at=None,
            ))
            await setup.commit()

        async with sessions() as db:
            asset = await db.get(Asset, asset_id)
            await retire_asset(
                asset_id=asset_id,
                request=_request(),
                db=db,
                current_user=MagicMock(email="phase0@example.invalid"),
            )
            assert asset.lifecycle_status == "Retiré"
            assert asset.retired_at is not None

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            events = (
                await verify.execute(
                    select(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(asset_id),
                        AuditOutbox.payload["action"].astext == "RETIRE",
                    )
                )
            ).scalars().all()
            assert persisted.lifecycle_status == "Retiré"
            assert persisted.retired_at is not None
            assert len(events) == 1
    finally:
        await _cleanup(sessions, asset_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_retirement_rolls_back_when_audit_enqueue_fails(monkeypatch):
    from app.api.v1.endpoints import assets as assets_endpoint

    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_id = uuid4()
    monkeypatch.setattr(
        assets_endpoint,
        "enqueue_audit_event",
        AsyncMock(side_effect=RuntimeError("simulated audit outbox failure")),
    )
    try:
        async with sessions() as setup:
            setup.add(Asset(
                id=asset_id,
                reference=f"PHASE0-RETIRE-ROLLBACK-{asset_id.hex[:8]}",
                name="Phase 0 retirement rollback",
                asset_type="hardware",
                lifecycle_status="Actif",
                retired_at=None,
            ))
            await setup.commit()

        async with sessions() as db:
            with pytest.raises(RuntimeError, match="simulated audit outbox failure"):
                await retire_asset(
                    asset_id=asset_id,
                    request=_request(),
                    db=db,
                    current_user=MagicMock(email="phase0@example.invalid"),
                )

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            events = (
                await verify.execute(
                    select(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(asset_id),
                        AuditOutbox.payload["action"].astext == "RETIRE",
                    )
                )
            ).scalars().all()
            assert persisted.lifecycle_status == "Actif"
            assert persisted.retired_at is None
            assert events == []
    finally:
        await _cleanup(sessions, asset_id)
        await engine.dispose()

@pytest.mark.asyncio
async def test_asset_reactivation_and_audit_event_commit_together():
    from app.api.v1.endpoints.assets import AssetUpdate, update_asset

    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_id = uuid4()
    try:
        async with sessions() as setup:
            setup.add(Asset(
                id=asset_id,
                reference=f"PHASE0-REACTIVATE-{asset_id.hex[:10]}",
                name="Phase 0 reactivation transaction",
                asset_type="hardware",
                lifecycle_status="Retiré",
                retired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ))
            await setup.commit()

        async with sessions() as db:
            await update_asset(
                asset_id=asset_id,
                data=AssetUpdate(lifecycle_status="Actif"),
                request=_request(),
                db=db,
                current_user=MagicMock(email="phase0@example.invalid"),
            )

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            events = (
                await verify.execute(
                    select(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(asset_id),
                        AuditOutbox.payload["action"].astext == "REACTIVATE",
                    )
                )
            ).scalars().all()
            assert persisted.lifecycle_status == "Actif"
            assert persisted.retired_at is None
            assert len(events) == 1
    finally:
        await _cleanup(sessions, asset_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_reactivation_rolls_back_when_audit_enqueue_fails(monkeypatch):
    from app.api.v1.endpoints import assets as assets_endpoint
    from app.api.v1.endpoints.assets import AssetUpdate, update_asset

    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_id = uuid4()
    monkeypatch.setattr(
        assets_endpoint,
        "enqueue_audit_event",
        AsyncMock(side_effect=RuntimeError("simulated reactivation audit failure")),
    )
    try:
        async with sessions() as setup:
            setup.add(Asset(
                id=asset_id,
                reference=f"PHASE0-REACTIVATE-ROLLBACK-{asset_id.hex[:8]}",
                name="Phase 0 reactivation rollback",
                asset_type="hardware",
                lifecycle_status="Décommissionné",
                retired_at=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            ))
            await setup.commit()

        async with sessions() as db:
            with pytest.raises(RuntimeError, match="simulated reactivation audit failure"):
                await update_asset(
                    asset_id=asset_id,
                    data=AssetUpdate(lifecycle_status="Actif"),
                    request=_request(),
                    db=db,
                    current_user=MagicMock(email="phase0@example.invalid"),
                )

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            events = (
                await verify.execute(
                    select(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(asset_id),
                        AuditOutbox.payload["action"].astext == "REACTIVATE",
                    )
                )
            ).scalars().all()
            assert persisted.lifecycle_status == "Décommissionné"
            assert persisted.retired_at is not None
            assert events == []
    finally:
        await _cleanup(sessions, asset_id)
        await engine.dispose()

@pytest.mark.asyncio
async def test_asset_retirement_is_blocked_by_open_supplier_access_request():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    asset_id = uuid4()
    supplier_id = uuid4()
    link_id = uuid4()
    access_id = uuid4()
    user = User(
        id=user_id,
        email=f"phase0-retire-access-{user_id.hex}@example.invalid",
        full_name="Phase 0 access guard",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        id=supplier_id,
        code=f"PH0-RET-{user_id.hex[:10]}",
        legal_name="Phase 0 retirement guard supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        id=asset_id,
        reference=f"PH0-RET-ACCESS-{user_id.hex[:8]}",
        name="Phase 0 asset with open supplier access",
        asset_type="hardware",
        lifecycle_status="Actif",
        retired_at=None,
    )
    link = SupplierAssetLink(
        id=link_id,
        supplier_id=supplier_id,
        asset_id=asset_id,
        relationship_type="Maintient",
        access_level="Standard",
        data_access=False,
        status="Actif",
        created_by_id=user_id,
    )
    today = datetime.now(timezone.utc).date()
    access = SupplierAccessRequest(
        id=access_id,
        supplier_id=supplier_id,
        supplier_asset_link_id=link_id,
        asset_id=asset_id,
        access_level="Standard",
        data_access=False,
        justification="Maintenance autorisée",
        scope="Intervention limitée",
        start_date=today,
        end_date=today + __import__("datetime").timedelta(days=30),
        review_due_at=today + __import__("datetime").timedelta(days=15),
        status="Approuvé",
        requested_by_id=user_id,
        decided_by_id=user_id,
        decided_at=datetime.now(timezone.utc),
    )
    try:
        async with sessions() as setup:
            setup.add(user)
            await setup.flush()
            setup.add_all([supplier, asset])
            await setup.flush()
            setup.add(link)
            await setup.flush()
            setup.add(access)
            await setup.commit()

        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await retire_asset(
                    asset_id=asset_id,
                    request=_request(),
                    db=db,
                    current_user=MagicMock(email=user.email),
                )
            assert exc.value.status_code == 409

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            assert persisted.lifecycle_status == "Actif"
            assert persisted.retired_at is None
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(SupplierAccessRequest).where(SupplierAccessRequest.id == access_id))
            await cleanup.execute(delete(SupplierAssetLink).where(SupplierAssetLink.id == link_id))
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()



@pytest.mark.asyncio
async def test_asset_retirement_is_blocked_by_active_supplier_asset_link():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    asset_id = uuid4()
    supplier_id = uuid4()
    link_id = uuid4()
    user = User(
        id=user_id,
        email=f"phase0-active-link-{user_id.hex}@example.invalid",
        full_name="Phase 0 active supplier link guard",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        id=supplier_id,
        code=f"PH0-LINK-{user_id.hex[:10]}",
        legal_name="Phase 0 active link supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        id=asset_id,
        reference=f"PH0-LINK-ASSET-{user_id.hex[:8]}",
        name="Phase 0 asset with active supplier link",
        asset_type="hardware",
        lifecycle_status="Actif",
        retired_at=None,
    )
    link = SupplierAssetLink(
        id=link_id,
        supplier_id=supplier_id,
        asset_id=asset_id,
        relationship_type="Maintient",
        access_level="Standard",
        data_access=False,
        status="Actif",
        created_by_id=user_id,
    )
    try:
        async with sessions() as setup:
            setup.add(user)
            await setup.flush()
            setup.add_all([supplier, asset])
            await setup.flush()
            setup.add(link)
            await setup.commit()

        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await retire_asset(
                    asset_id=asset_id,
                    request=_request(),
                    db=db,
                    current_user=MagicMock(email=user.email),
                )
            assert exc.value.status_code == 409

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            assert persisted.lifecycle_status == "Actif"
            assert persisted.retired_at is None
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(SupplierAssetLink).where(SupplierAssetLink.id == link_id))
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()
