"""PostgreSQL transaction tests for asset retirement and audit consistency."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.assets import AssetUpdate, retire_asset, update_asset
from app.models.asset import Asset
from app.models.audit_outbox import AuditOutbox
from app.models.supplier import Supplier, SupplierAccessRequest, SupplierAssetLink
from app.models.user import User
from app.api.v1.endpoints.suppliers import (
    SupplierAccessRequestCreate,
    SupplierAssetLinkCreate,
    create_supplier_access_request,
    link_supplier_asset,
    terminate_supplier_asset_link,
)


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


@pytest.mark.asyncio
async def test_supplier_link_creation_and_asset_retirement_are_serialized():
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    asset_id = uuid4()
    supplier_id = uuid4()
    user = User(
        id=user_id,
        email=f"phase0-link-race-{user_id.hex}@example.invalid",
        full_name="Phase 0 relationship race",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        id=supplier_id,
        code=f"PH0-RACE-{user_id.hex[:10]}",
        legal_name="Phase 0 relationship race supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        id=asset_id,
        reference=f"PH0-RACE-ASSET-{user_id.hex[:8]}",
        name="Phase 0 relationship race asset",
        asset_type="hardware",
        lifecycle_status="Actif",
        retired_at=None,
    )
    try:
        async with sessions() as setup:
            setup.add(user)
            await setup.flush()
            setup.add_all([supplier, asset])
            await setup.commit()

        async def create_link():
            async with sessions() as db:
                try:
                    await link_supplier_asset(
                        supplier_id=supplier_id,
                        data=SupplierAssetLinkCreate(
                            asset_id=asset_id,
                            relationship_type="Maintient",
                            access_level="Standard",
                        ),
                        request=_request(),
                        db=db,
                        current_user=MagicMock(id=user_id, email=user.email),
                    )
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        async def retire():
            async with sessions() as db:
                try:
                    await retire_asset(
                        asset_id=asset_id,
                        request=_request(),
                        db=db,
                        current_user=MagicMock(email=user.email),
                    )
                    return 204
                except HTTPException as exc:
                    return exc.status_code

        outcomes = await asyncio.gather(create_link(), retire())
        assert outcomes in ([201, 409], [422, 204])

        async with sessions() as verify:
            persisted_asset = await verify.get(Asset, asset_id)
            active_link = (
                await verify.execute(
                    select(SupplierAssetLink.id).where(
                        SupplierAssetLink.asset_id == asset_id,
                        SupplierAssetLink.status == "Actif",
                    )
                )
            ).scalar_one_or_none()
            assert (persisted_asset.lifecycle_status == "Retiré") == (active_link is None)
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(SupplierAssetLink).where(SupplierAssetLink.asset_id == asset_id))
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()

@pytest.mark.asyncio
async def test_asset_patch_retirement_is_blocked_by_active_supplier_asset_link():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    asset_id = uuid4()
    supplier_id = uuid4()
    link_id = uuid4()
    user = User(
        id=user_id,
        email=f"phase0-patch-retire-{user_id.hex}@example.invalid",
        full_name="Phase 0 patch retirement guard",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        id=supplier_id,
        code=f"PH0-PATCH-{user_id.hex[:10]}",
        legal_name="Phase 0 patch retirement supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        id=asset_id,
        reference=f"PH0-PATCH-ASSET-{user_id.hex[:8]}",
        name="Phase 0 patch retirement guarded asset",
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
                await update_asset(
                    asset_id=asset_id,
                    data=AssetUpdate(lifecycle_status="Décommissionné"),
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

@pytest.mark.asyncio
async def test_asset_risk_link_is_preserved_as_history_after_retirement_and_new_link_is_rejected():
    """Risk associations remain historical; retirement blocks only new associations."""
    from app.api.v1.endpoints.assets import AssetRiskLinkCreate, link_asset_to_risk
    from app.models.asset import AssetRiskLink
    from app.models.risk import Risk

    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_id = uuid4()
    risk_id = uuid4()
    asset_reference = f"PH0-RISK-LIFECYCLE-{asset_id.hex[:8]}"
    risk_reference = f"PH0-RISK-LIFECYCLE-{risk_id.hex[:8]}"
    try:
        async with sessions() as setup:
            setup.add_all([
                Asset(
                    id=asset_id,
                    reference=asset_reference,
                    name="Asset with historical risk association",
                    asset_type="hardware",
                    lifecycle_status="Actif",
                    retired_at=None,
                ),
                Risk(
                    id=risk_id,
                    ref=risk_reference,
                    title="Risk linked to lifecycle test asset",
                    impact=3,
                    likelihood=3,
                    risk_level=9,
                    status="Ouvert",
                ),
            ])
            await setup.commit()

        async with sessions() as db:
            await link_asset_to_risk(
                asset_id=asset_id,
                data=AssetRiskLinkCreate(
                    risk_id=risk_id,
                    relationship_context="Association conservée pour l'historique du risque",
                ),
                request=_request(),
                db=db,
                current_user=MagicMock(role="admin", email="phase0-risk@example.invalid"),
            )

        async with sessions() as db:
            await retire_asset(
                asset_id=asset_id,
                request=_request(),
                db=db,
                current_user=MagicMock(email="phase0-risk@example.invalid"),
            )

        async with sessions() as verify:
            persisted_asset = await verify.get(Asset, asset_id)
            links = (
                await verify.execute(
                    select(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id)
                )
            ).scalars().all()
            assert persisted_asset.lifecycle_status == "Retiré"
            assert persisted_asset.retired_at is not None
            assert len(links) == 1
            assert links[0].risk_id == risk_id

        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await link_asset_to_risk(
                    asset_id=asset_id,
                    data=AssetRiskLinkCreate(risk_id=risk_id),
                    request=_request(),
                    db=db,
                    current_user=MagicMock(role="admin", email="phase0-risk@example.invalid"),
                )
            assert exc.value.status_code == 409

        async with sessions() as verify:
            links = (
                await verify.execute(
                    select(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id)
                )
            ).scalars().all()
            assert len(links) == 1
    finally:
        async with sessions() as cleanup:
            link_ids = (
                await cleanup.execute(
                    select(AssetRiskLink.id).where(AssetRiskLink.asset_id == asset_id)
                )
            ).scalars().all()
            if link_ids:
                await cleanup.execute(
                    delete(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext.in_(
                            [str(link_id) for link_id in link_ids]
                        )
                    )
                )
                await cleanup.execute(
                    delete(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id)
                )
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Risk).where(Risk.id == risk_id))
            await cleanup.commit()
        await engine.dispose()

@pytest.mark.asyncio
async def test_application_supports_multiple_assets_reassignment_and_restrictive_delete():
    """One application may own many assets; referenced applications cannot be deleted."""
    from sqlalchemy.exc import IntegrityError
    from app.api.v1.endpoints.assets import AssetCreate, create_asset
    from app.models.application import Application

    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    application_a_id = uuid4()
    application_b_id = uuid4()
    asset_a_id = uuid4()
    asset_b_id = uuid4()
    user = MagicMock(email="phase1-application-cardinality@example.invalid")
    try:
        async with sessions() as setup:
            setup.add_all([
                Application(id=application_a_id, name=f"Phase1 app A {application_a_id.hex[:8]}"),
                Application(id=application_b_id, name=f"Phase1 app B {application_b_id.hex[:8]}"),
            ])
            await setup.commit()

        async with sessions() as db:
            asset_a = await create_asset(
                data=AssetCreate(
                    reference=f"PH1-APP-A-{asset_a_id.hex[:8]}",
                    name="First technical asset",
                    asset_type="hardware",
                    application_id=application_a_id,
                ),
                request=_request(),
                db=db,
                current_user=user,
            )
            asset_a_id = asset_a.id

        async with sessions() as db:
            asset_b = await create_asset(
                data=AssetCreate(
                    reference=f"PH1-APP-B-{asset_b_id.hex[:8]}",
                    name="Second technical asset",
                    asset_type="software",
                    application_id=application_a_id,
                ),
                request=_request(),
                db=db,
                current_user=user,
            )
            asset_b_id = asset_b.id

        async with sessions() as verify:
            linked_ids = (
                await verify.execute(
                    select(Asset.id).where(Asset.application_id == application_a_id)
                )
            ).scalars().all()
            assert set(linked_ids) == {asset_a_id, asset_b_id}

        async with sessions() as db:
            await update_asset(
                asset_id=asset_b_id,
                data=AssetUpdate(application_id=application_b_id),
                request=_request(),
                db=db,
                current_user=user,
            )

        async with sessions() as verify:
            asset_a = await verify.get(Asset, asset_a_id)
            asset_b = await verify.get(Asset, asset_b_id)
            assert asset_a.application_id == application_a_id
            assert asset_b.application_id == application_b_id

        for application_id in (application_a_id, application_b_id):
            async with sessions() as db:
                with pytest.raises(IntegrityError):
                    await db.execute(
                        delete(Application).where(Application.id == application_id)
                    )
                    await db.commit()
                await db.rollback()

    finally:
        async with sessions() as cleanup:
            asset_ids = [asset_a_id, asset_b_id]
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext.in_(
                        [str(asset_id) for asset_id in asset_ids]
                    )
                )
            )
            await cleanup.execute(delete(Asset).where(Asset.id.in_(asset_ids)))
            await cleanup.execute(
                delete(Application).where(
                    Application.id.in_([application_a_id, application_b_id])
                )
            )
            await cleanup.commit()
        await engine.dispose()

@pytest.mark.asyncio
async def test_asset_reactivation_preserves_application_and_historical_risk_link():
    from app.models.application import Application
    from app.models.asset import AssetRiskLink
    from app.models.risk import Risk

    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    application_id = uuid4()
    asset_id = uuid4()
    risk_id = uuid4()
    asset_reference = f"PH1-REACTIVATE-APP-{asset_id.hex[:8]}"
    risk_reference = f"PH1-REACTIVATE-RISK-{risk_id.hex[:8]}"
    try:
        async with sessions() as setup:
            setup.add_all([
                Application(id=application_id, name=f"Reactivation app {application_id.hex[:8]}"),
                Risk(
                    id=risk_id,
                    ref=risk_reference,
                    title="Historical risk association during asset reactivation",
                    impact=3,
                    likelihood=3,
                    risk_level=9,
                    status="Ouvert",
                ),
                Asset(
                    id=asset_id,
                    reference=asset_reference,
                    name="Retired asset with application and risk history",
                    asset_type="hardware",
                    application_id=application_id,
                    lifecycle_status="Retiré",
                    retired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
            ])
            await setup.flush()
            setup.add(AssetRiskLink(
                asset_id=asset_id,
                risk_id=risk_id,
                relationship_context="Historique conservé pendant le retrait",
            ))
            await setup.commit()

        async with sessions() as db:
            await update_asset(
                asset_id=asset_id,
                data=AssetUpdate(lifecycle_status="Actif"),
                request=_request(),
                db=db,
                current_user=MagicMock(email="phase1-reactivation@example.invalid"),
            )

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_id)
            links = (
                await verify.execute(
                    select(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id)
                )
            ).scalars().all()
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
            assert persisted.application_id == application_id
            assert len(links) == 1
            assert links[0].risk_id == risk_id
            assert len(events) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext == str(asset_id)
                )
            )
            await cleanup.execute(delete(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id))
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Risk).where(Risk.id == risk_id))
            await cleanup.execute(delete(Application).where(Application.id == application_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_risk_link_creation_and_retirement_are_serialized():
    """A concurrent risk link cannot be committed after the asset is retired."""
    from app.api.v1.endpoints.assets import AssetRiskLinkCreate, link_asset_to_risk
    from app.models.asset import AssetRiskLink
    from app.models.risk import Risk

    engine = create_async_engine(DATABASE_URL, pool_size=4, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_id = uuid4()
    risk_id = uuid4()
    asset = Asset(
        id=asset_id,
        reference=f"PH1-RISK-RACE-ASSET-{asset_id.hex[:8]}",
        name="Asset risk-link retirement race",
        asset_type="hardware",
        lifecycle_status="Actif",
        retired_at=None,
    )
    risk = Risk(
        id=risk_id,
        ref=f"PH1-RISK-RACE-{risk_id.hex[:8]}",
        title="Risk link versus asset retirement",
        impact=3,
        likelihood=3,
        risk_level=9,
        status="Ouvert",
    )
    user = MagicMock(role="admin", email="phase1-risk-race@example.invalid")
    try:
        async with sessions() as setup:
            setup.add_all([asset, risk])
            await setup.commit()

        async def create_risk_link():
            async with sessions() as db:
                try:
                    await link_asset_to_risk(
                        asset_id=asset_id,
                        data=AssetRiskLinkCreate(
                            risk_id=risk_id,
                            relationship_context="Concurrent lifecycle serialization test",
                        ),
                        request=_request(),
                        db=db,
                        current_user=user,
                    )
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        async def retire():
            async with sessions() as db:
                try:
                    await retire_asset(
                        asset_id=asset_id,
                        request=_request(),
                        db=db,
                        current_user=user,
                    )
                    return 204
                except HTTPException as exc:
                    return exc.status_code

        link_status, retirement_status = await asyncio.gather(
            create_risk_link(), retire()
        )
        assert link_status in (201, 409)
        assert retirement_status == 204

        async with sessions() as verify:
            persisted_asset = await verify.get(Asset, asset_id)
            persisted_links = (
                await verify.execute(
                    select(AssetRiskLink).where(
                        AssetRiskLink.asset_id == asset_id,
                        AssetRiskLink.risk_id == risk_id,
                    )
                )
            ).scalars().all()
            assert persisted_asset.lifecycle_status == "Retiré"
            assert persisted_asset.retired_at is not None
            assert len(persisted_links) == (1 if link_status == 201 else 0)
    finally:
        async with sessions() as cleanup:
            link_ids = (
                await cleanup.execute(
                    select(AssetRiskLink.id).where(AssetRiskLink.asset_id == asset_id)
                )
            ).scalars().all()
            audit_resource_ids = [str(asset_id), *[str(link_id) for link_id in link_ids]]
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext.in_(audit_resource_ids)
                )
            )
            await cleanup.execute(
                delete(AssetRiskLink).where(AssetRiskLink.asset_id == asset_id)
            )
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Risk).where(Risk.id == risk_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_supplier_access_request_creation_and_link_termination_are_serialized():
    """An access request cannot become open after its supplier-asset link is terminated."""
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, supplier_id, asset_id, link_id = uuid4(), uuid4(), uuid4(), uuid4()
    user = User(
        id=user_id,
        email=f"phase1-access-race-{user_id.hex}@example.invalid",
        full_name="Phase 1 supplier access race",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        id=supplier_id,
        code=f"PH1-ACCESS-RACE-{user_id.hex[:8]}",
        legal_name="Phase 1 access race supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        id=asset_id,
        reference=f"PH1-ACCESS-RACE-{asset_id.hex[:8]}",
        name="Supplier access request versus supplier-link termination",
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
    try:
        async with sessions() as setup:
            setup.add(user)
            await setup.flush()
            setup.add_all([supplier, asset])
            await setup.flush()
            setup.add(link)
            await setup.commit()

        async def request_access():
            async with sessions() as db:
                try:
                    await create_supplier_access_request(
                        supplier_id=supplier_id,
                        data=SupplierAccessRequestCreate(
                            supplier_asset_link_id=link_id,
                            access_level="Standard",
                            data_access=False,
                            justification="Maintenance planifiée sur cet actif",
                            scope="Intervention technique limitée",
                            start_date=today,
                            end_date=today + timedelta(days=30),
                            review_due_at=today + timedelta(days=15),
                        ),
                        request=_request(),
                        db=db,
                        current_user=MagicMock(id=user_id, email=user.email),
                    )
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        async def terminate_link():
            async with sessions() as db:
                try:
                    await terminate_supplier_asset_link(
                        supplier_id=supplier_id,
                        link_id=link_id,
                        request=_request(),
                        db=db,
                        current_user=MagicMock(email=user.email),
                    )
                    return 200
                except HTTPException as exc:
                    return exc.status_code

        outcomes = await asyncio.gather(request_access(), terminate_link())
        assert outcomes in ([201, 409], [404, 200])

        async with sessions() as verify:
            persisted_link = await verify.get(SupplierAssetLink, link_id)
            open_requests = (
                await verify.execute(
                    select(SupplierAccessRequest.id).where(
                        SupplierAccessRequest.supplier_asset_link_id == link_id,
                        SupplierAccessRequest.status.in_(("Demandé", "Approuvé", "Suspendu")),
                    )
                )
            ).scalars().all()
            assert (persisted_link.status == "Terminé") == (not open_requests)
    finally:
        async with sessions() as cleanup:
            request_ids = (
                await cleanup.execute(
                    select(SupplierAccessRequest.id).where(
                        SupplierAccessRequest.asset_id == asset_id
                    )
                )
            ).scalars().all()
            audit_ids = [str(asset_id), str(link_id), *[str(item) for item in request_ids]]
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext.in_(audit_ids)
                )
            )
            await cleanup.execute(
                delete(SupplierAccessRequest).where(
                    SupplierAccessRequest.asset_id == asset_id
                )
            )
            await cleanup.execute(
                delete(SupplierAssetLink).where(SupplierAssetLink.asset_id == asset_id)
            )
            await cleanup.execute(delete(Asset).where(Asset.id == asset_id))
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()
