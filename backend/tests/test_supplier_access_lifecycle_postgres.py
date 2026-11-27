"""PostgreSQL concurrency coverage for supplier access and link termination."""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.action_item import ActionItem  # register Risk.actions mapper target
from app.models.asset import Asset
from app.models.audit_outbox import AuditOutbox
from app.models.supplier import Supplier, SupplierAccessRequest, SupplierAssetLink
from app.models.user import User
from app.api.v1.endpoints.suppliers import (
    SupplierAccessRequestCreate,
    SupplierAccessRevocation,
    create_supplier_access_request,
    revoke_supplier_access_request,
    terminate_supplier_asset_link,
)

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")


def _request():
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/phase0-supplier-test",
        "headers": [(b"user-agent", b"phase0-supplier-postgres-test")],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 80),
        "scheme": "http",
        "query_string": b"",
    })

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_access_request_creation_and_link_termination_are_serialized(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"phase0-supplier-{user_id.hex}@example.invalid",
        full_name="Phase 0 supplier access test",
        role="viewer",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        code=f"PH0-{user_id.hex[:12]}",
        legal_name="Phase 0 supplier access concurrency",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        reference=f"PH0-SUP-{user_id.hex[:12]}",
        name="Phase 0 supplier access asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )

    link = None
    try:
        async with sessions() as setup:
            setup.add(user)
            await setup.commit()
            setup.add_all([supplier, asset])
            await setup.commit()
            await setup.refresh(supplier)
            await setup.refresh(asset)
            link = SupplierAssetLink(
                supplier_id=supplier.id,
                asset_id=asset.id,
                relationship_type="Maintient",
                access_level="Standard",
                data_access=False,
                status="Actif",
                created_by_id=user_id,
            )
            setup.add(link)
            await setup.commit()
            await setup.refresh(link)

        today = date.today()
        request_data = SupplierAccessRequestCreate(
            supplier_asset_link_id=link.id,
            access_level="Standard",
            data_access=False,
            justification="Maintenance ponctuelle validée",
            scope="Intervention sur le serveur",
            start_date=today,
            end_date=today + timedelta(days=30),
            review_due_at=today + timedelta(days=15),
        )

        async def create_request():
            async with sessions() as db:
                try:
                    await create_supplier_access_request(
                        supplier_id=supplier.id,
                        data=request_data,
                        request=_request(),
                        db=db,
                        current_user=MagicMock(id=user_id, email=user.email),
                    )
                    return ("request", 201)
                except HTTPException as exc:
                    return ("request", exc.status_code)

        async def terminate_link():
            async with sessions() as db:
                try:
                    await terminate_supplier_asset_link(
                        supplier_id=supplier.id,
                        link_id=link.id,
                        request=_request(),
                        db=db,
                        current_user=MagicMock(id=user_id, email=user.email),
                    )
                    return ("terminate", 200)
                except HTTPException as exc:
                    return ("terminate", exc.status_code)

        outcomes = await asyncio.gather(create_request(), terminate_link())
        outcome_codes = {name: code for name, code in outcomes}
        assert (
            outcome_codes == {"request": 201, "terminate": 409}
            or outcome_codes == {"request": 404, "terminate": 200}
        )

        async with sessions() as verify:
            final_link = (await verify.execute(
                select(SupplierAssetLink).where(SupplierAssetLink.id == link.id)
            )).scalar_one()
            open_request = (await verify.execute(
                select(SupplierAccessRequest.id).where(
                    SupplierAccessRequest.supplier_asset_link_id == link.id,
                    SupplierAccessRequest.status.in_(("Demandé", "Approuvé", "Suspendu")),
                )
            )).scalar_one_or_none()
            assert (final_link.status == "Actif") == (open_request is not None)
    finally:
        if link is not None:
            async with sessions() as cleanup:
                await cleanup.execute(delete(SupplierAccessRequest).where(
                    SupplierAccessRequest.supplier_asset_link_id == link.id
                ))
                await cleanup.execute(delete(SupplierAssetLink).where(
                    SupplierAssetLink.id == link.id
                ))
                await cleanup.execute(delete(Asset).where(Asset.id == asset.id))
                await cleanup.execute(delete(Supplier).where(Supplier.id == supplier.id))
                await cleanup.execute(delete(User).where(User.id == user_id))
                await cleanup.commit()
        await engine.dispose()



@pytest.mark.asyncio
async def test_approved_access_blocks_link_termination_until_revocation():
    """An approved authorization must be closed before its supplier link can end."""
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor = User(
        id=actor_id,
        email=f"phase0-revoke-{actor_id.hex}@example.com",
        full_name="Phase 0 supplier revocation test",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        code=f"PH0-RV-{actor_id.hex[:10]}",
        legal_name="Phase 0 approved access revocation",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        reference=f"PH0-RV-{actor_id.hex[:10]}",
        name="Phase 0 revocation asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    link = None
    access_request = None
    try:
        async with sessions() as setup:
            setup.add(actor)
            await setup.flush()
            setup.add_all([supplier, asset])
            await setup.flush()
            link = SupplierAssetLink(
                supplier_id=supplier.id,
                asset_id=asset.id,
                relationship_type="Maintient",
                access_level="Standard",
                data_access=False,
                status="Actif",
                created_by_id=actor_id,
            )
            setup.add(link)
            await setup.flush()
            today = date.today()
            access_request = SupplierAccessRequest(
                supplier_id=supplier.id,
                supplier_asset_link_id=link.id,
                asset_id=asset.id,
                access_level="Standard",
                data_access=False,
                justification="Accès de maintenance autorisé",
                scope="Maintenance du serveur",
                start_date=today,
                end_date=today + timedelta(days=30),
                review_due_at=today + timedelta(days=15),
                status="Approuvé",
                requested_by_id=actor_id,
                decided_by_id=actor_id,
                decided_at=datetime.now(timezone.utc),
                decision_comment="Approbation initiale de test",
            )
            setup.add(access_request)
            await setup.commit()
            await setup.refresh(link)
            await setup.refresh(access_request)

        async with sessions() as db:
            with pytest.raises(HTTPException) as blocked:
                await terminate_supplier_asset_link(
                    supplier_id=supplier.id,
                    link_id=link.id,
                    request=_request(),
                    db=db,
                    current_user=MagicMock(id=actor_id, email=actor.email),
                )
            assert blocked.value.status_code == 409
            await db.rollback()

        async with sessions() as db:
            revoked = await revoke_supplier_access_request(
                supplier_id=supplier.id,
                access_request_id=access_request.id,
                data=SupplierAccessRevocation(reason="Fin du besoin opérationnel"),
                request=_request(),
                db=db,
                current_user=MagicMock(id=actor_id, email=actor.email),
            )
            assert revoked.status == "Révoqué"
            assert revoked.revoked_by_id == actor_id
            assert revoked.revoked_at is not None

        async with sessions() as db:
            terminated = await terminate_supplier_asset_link(
                supplier_id=supplier.id,
                link_id=link.id,
                request=_request(),
                db=db,
                current_user=MagicMock(id=actor_id, email=actor.email),
            )
            assert terminated.status == "Terminé"

        async with sessions() as verify:
            persisted_request = await verify.get(SupplierAccessRequest, access_request.id)
            persisted_link = await verify.get(SupplierAssetLink, link.id)
            audit_actions = (
                await verify.execute(
                    select(AuditOutbox.payload["action"].astext).where(
                        AuditOutbox.payload["resource_id"].astext.in_(
                            [str(access_request.id), str(link.id)]
                        )
                    )
                )
            ).scalars().all()
            assert persisted_request.status == "Révoqué"
            assert persisted_link.status == "Terminé"
            assert "REVOKE_SUPPLIER_ACCESS" in audit_actions
            assert "TERMINATE_SUPPLIER_ASSET_LINK" in audit_actions
    finally:
        async with sessions() as cleanup:
            if access_request is not None:
                await cleanup.execute(
                    delete(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(access_request.id)
                    )
                )
                await cleanup.execute(
                    delete(SupplierAccessRequest).where(
                        SupplierAccessRequest.id == access_request.id
                    )
                )
            if link is not None:
                await cleanup.execute(
                    delete(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(link.id)
                    )
                )
                await cleanup.execute(
                    delete(SupplierAssetLink).where(SupplierAssetLink.id == link.id)
                )
            await cleanup.execute(delete(Asset).where(Asset.id == asset.id))
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier.id))
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()
