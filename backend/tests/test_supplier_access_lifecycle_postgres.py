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
from app.models.supplier import Supplier, SupplierAccessRequest, SupplierAccessReview, SupplierAssetLink
from app.models.user import User
from app.api.v1.endpoints.suppliers import (
    SupplierAccessRequestCreate,
    SupplierAccessRevocation,
    create_supplier_access_request,
    expire_supplier_access_request,
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

@pytest.mark.asyncio
async def test_expired_approved_access_can_be_expired_before_link_termination():
    """An approved but elapsed authorization must be explicitly expired before link closure."""
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor = User(
        id=actor_id,
        email=f"phase0-expire-{actor_id.hex}@example.com",
        full_name="Phase 0 supplier access expiration test",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        code=f"PH0-EX-{actor_id.hex[:10]}",
        legal_name="Phase 0 expired access lifecycle",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        reference=f"PH0-EX-{actor_id.hex[:10]}",
        name="Phase 0 expiration asset",
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
            yesterday = date.today() - timedelta(days=1)
            access_request = SupplierAccessRequest(
                supplier_id=supplier.id,
                supplier_asset_link_id=link.id,
                asset_id=asset.id,
                access_level="Standard",
                data_access=False,
                justification="Accès de maintenance temporaire",
                scope="Maintenance du serveur",
                start_date=yesterday - timedelta(days=30),
                end_date=yesterday,
                review_due_at=yesterday,
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
            expired = await expire_supplier_access_request(
                supplier_id=supplier.id,
                access_request_id=access_request.id,
                request=_request(),
                db=db,
                current_user=MagicMock(id=actor_id, email=actor.email),
            )
            assert expired.status == "Expiré"

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
            assert persisted_request.status == "Expiré"
            assert persisted_link.status == "Terminé"
            assert "EXPIRE_SUPPLIER_ACCESS" in audit_actions
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


@pytest.mark.asyncio
async def test_supplier_access_http_jwt_uses_real_postgres_user_and_supplier(monkeypatch):
    """Exercise the real HTTP/JWT dependency chain against migrated PostgreSQL."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import suppliers as suppliers_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-postgres-http-jwt-secret-long-enough"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id = uuid4()
    actor_email = f"phase0-http-jwt-{actor_id.hex}@example.invalid"
    actor = User(
        id=actor_id,
        email=actor_email,
        full_name="Phase 0 HTTP JWT PostgreSQL auditor",
        role="auditor",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=False,
        auth_version=7,
    )
    supplier = Supplier(
        code=f"PH0-HTTP-{actor_id.hex[:10]}",
        legal_name="Phase 0 HTTP JWT supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )

    try:
        async with sessions() as setup:
            setup.add_all([actor, supplier])
            await setup.commit()
            await setup.refresh(supplier)

        app = FastAPI()
        app.include_router(suppliers_endpoint.router, prefix="/api/v1")

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        token = create_access_token(
            subject=actor_email, role="auditor", auth_version=7
        )
        headers = {"Authorization": f"Bearer {token}"}
        supplier_id = str(supplier.id)
        with TestClient(app) as client:
            read_response = client.get(
                f"/api/v1/suppliers/{supplier_id}/access-requests",
                headers=headers,
            )
            assert read_response.status_code == 200
            assert read_response.json() == []

            write_response = client.post(
                f"/api/v1/suppliers/{supplier_id}/access-requests",
                headers=headers,
                json={
                    "supplier_asset_link_id": str(uuid4()),
                    "access_level": "Standard",
                    "data_access": False,
                    "justification": "Intervention technique planifiée",
                    "scope": "Maintenance applicative",
                    "start_date": date.today().isoformat(),
                    "end_date": (date.today() + timedelta(days=30)).isoformat(),
                    "review_due_at": (date.today() + timedelta(days=15)).isoformat(),
                },
            )
            assert write_response.status_code == 403

        async with sessions() as verify:
            persisted = await verify.execute(
                select(SupplierAccessRequest.id).where(
                    SupplierAccessRequest.supplier_id == supplier.id
                )
            )
            assert persisted.scalar_one_or_none() is None
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(SupplierAccessRequest).where(
                    SupplierAccessRequest.supplier_id == supplier.id
                )
            )
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier.id))
            await cleanup.execute(delete(User).where(User.id == actor_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_supplier_access_full_lifecycle_over_http_with_real_jwt_and_postgres(monkeypatch):
    """Create, approve, revoke and terminate through HTTP using persisted JWT users."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import suppliers as suppliers_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-postgres-lifecycle-jwt-secret-long-enough"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    requester_id, approver_id = uuid4(), uuid4()
    requester = User(
        id=requester_id,
        email=f"phase0-lifecycle-requester-{requester_id.hex}@example.invalid",
        full_name="Phase 0 lifecycle requester",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=1,
    )
    approver = User(
        id=approver_id,
        email=f"phase0-lifecycle-approver-{approver_id.hex}@example.invalid",
        full_name="Phase 0 lifecycle approver",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=1,
    )
    supplier = Supplier(
        code=f"PH0-LIFE-{requester_id.hex[:10]}",
        legal_name="Phase 0 HTTP supplier access lifecycle",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        reference=f"PH0-LIFE-{requester_id.hex[:10]}",
        name="Phase 0 HTTP lifecycle asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    link = None
    access_request_id = None
    try:
        async with sessions() as setup:
            setup.add_all([requester, approver, supplier, asset])
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
                created_by_id=requester_id,
            )
            setup.add(link)
            await setup.commit()
            await setup.refresh(link)

        app = FastAPI()
        app.include_router(suppliers_endpoint.router, prefix="/api/v1")

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        requester_token = create_access_token(
            subject=requester.email, role="admin", auth_version=1
        )
        approver_token = create_access_token(
            subject=approver.email, role="admin", auth_version=1
        )
        requester_headers = {"Authorization": f"Bearer {requester_token}"}
        approver_headers = {"Authorization": f"Bearer {approver_token}"}
        supplier_id = str(supplier.id)
        link_id = str(link.id)
        today = date.today()

        with TestClient(app) as client:
            created = client.post(
                f"/api/v1/suppliers/{supplier_id}/access-requests",
                headers=requester_headers,
                json={
                    "supplier_asset_link_id": link_id,
                    "access_level": "Standard",
                    "data_access": False,
                    "justification": "Maintenance ponctuelle autorisée",
                    "scope": "Intervention sur le serveur",
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=30)).isoformat(),
                    "review_due_at": (today + timedelta(days=15)).isoformat(),
                },
            )
            assert created.status_code == 201, created.text
            access_request_id = created.json()["id"]
            assert created.json()["status"] == "Demandé"

            decided = client.post(
                f"/api/v1/suppliers/{supplier_id}/access-requests/{access_request_id}/decision",
                headers=approver_headers,
                json={
                    "decision": "Approuvé",
                    "comment": "Autorisation validée après contrôle",
                },
            )
            assert decided.status_code == 200, decided.text
            assert decided.json()["status"] == "Approuvé"

            revoked = client.post(
                f"/api/v1/suppliers/{supplier_id}/access-requests/{access_request_id}/revoke",
                headers=approver_headers,
                json={"reason": "Fin du besoin opérationnel"},
            )
            assert revoked.status_code == 200, revoked.text
            assert revoked.json()["status"] == "Révoqué"

            terminated = client.post(
                f"/api/v1/suppliers/{supplier_id}/assets/{link_id}/terminate",
                headers=approver_headers,
            )
            assert terminated.status_code == 200, terminated.text
            assert terminated.json()["status"] == "Terminé"

        async with sessions() as verify:
            persisted_request = await verify.get(
                SupplierAccessRequest, access_request_id
            )
            persisted_link = await verify.get(SupplierAssetLink, link.id)
            audit_actions = (
                await verify.execute(
                    select(AuditOutbox.payload["action"].astext).where(
                        AuditOutbox.payload["resource_id"].astext.in_(
                            [access_request_id, link_id]
                        )
                    )
                )
            ).scalars().all()
            assert persisted_request.status == "Révoqué"
            assert persisted_request.decided_by_id == approver_id
            assert persisted_link.status == "Terminé"
            assert "CREATE_SUPPLIER_ACCESS_REQUEST" in audit_actions
            assert "REVOKE_SUPPLIER_ACCESS" in audit_actions
            assert "TERMINATE_SUPPLIER_ASSET_LINK" in audit_actions
    finally:
        async with sessions() as cleanup:
            resource_ids = [str(link.id)] if link is not None else []
            if access_request_id is not None:
                resource_ids.append(access_request_id)
            if resource_ids:
                await cleanup.execute(
                    delete(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext.in_(resource_ids)
                    )
                )
            if access_request_id is not None:
                await cleanup.execute(
                    delete(SupplierAccessRequest).where(
                        SupplierAccessRequest.id == access_request_id
                    )
                )
            if link is not None:
                await cleanup.execute(
                    delete(SupplierAssetLink).where(SupplierAssetLink.id == link.id)
                )
            await cleanup.execute(delete(Asset).where(Asset.id == asset.id))
            await cleanup.execute(delete(Supplier).where(Supplier.id == supplier.id))
            await cleanup.execute(
                delete(User).where(User.id.in_([requester_id, approver_id]))
            )
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_supplier_review_and_expiration_over_http_with_real_jwt_and_postgres(monkeypatch):
    """Exercise periodic review and expiry routes with persisted users and records."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import NullPool

    from app.api.v1.endpoints import suppliers as suppliers_endpoint
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.security import create_access_token

    monkeypatch.setattr(
        settings, "JWT_SECRET", "pgcc-postgres-review-expiry-jwt-secret-long"
    )
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    requester_id, approver_id, operator_id = uuid4(), uuid4(), uuid4()
    requester = User(
        id=requester_id,
        email=f"phase0-review-requester-{requester_id.hex}@example.invalid",
        full_name="Phase 0 review requester",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=1,
    )
    approver = User(
        id=approver_id,
        email=f"phase0-review-approver-{approver_id.hex}@example.invalid",
        full_name="Phase 0 review approver",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=1,
    )
    operator = User(
        id=operator_id,
        email=f"phase0-review-operator-{operator_id.hex}@example.invalid",
        full_name="Phase 0 review and expiry operator",
        role="admin",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
        auth_version=1,
    )
    review_supplier = Supplier(
        code=f"PH0-REV-{operator_id.hex[:10]}",
        legal_name="Phase 0 periodic review supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    review_asset = Asset(
        reference=f"PH0-REV-{operator_id.hex[:10]}",
        name="Phase 0 periodic review asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    expiry_supplier = Supplier(
        code=f"PH0-EXP-{operator_id.hex[:10]}",
        legal_name="Phase 0 expiration supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    expiry_asset = Asset(
        reference=f"PH0-EXP-{operator_id.hex[:10]}",
        name="Phase 0 expiration asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    review_link = expiry_link = None
    review_request_id = expiry_request_id = review_id = None
    try:
        async with sessions() as setup:
            setup.add_all([
                requester, approver, operator,
                review_supplier, review_asset, expiry_supplier, expiry_asset,
            ])
            await setup.commit()
            for item in (review_supplier, review_asset, expiry_supplier, expiry_asset):
                await setup.refresh(item)

            today = date.today()
            review_link = SupplierAssetLink(
                supplier_id=review_supplier.id,
                asset_id=review_asset.id,
                relationship_type="Maintient",
                access_level="Standard",
                data_access=False,
                status="Actif",
                created_by_id=requester_id,
            )
            expiry_link = SupplierAssetLink(
                supplier_id=expiry_supplier.id,
                asset_id=expiry_asset.id,
                relationship_type="Maintient",
                access_level="Standard",
                data_access=False,
                status="Actif",
                created_by_id=requester_id,
            )
            setup.add_all([review_link, expiry_link])
            await setup.flush()
            review_request = SupplierAccessRequest(
                supplier_id=review_supplier.id,
                supplier_asset_link_id=review_link.id,
                asset_id=review_asset.id,
                access_level="Standard",
                data_access=False,
                justification="Maintenance périodique autorisée",
                scope="Maintenance du serveur",
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=30),
                review_due_at=today + timedelta(days=10),
                status="Approuvé",
                requested_by_id=requester_id,
                decided_by_id=approver_id,
                decided_at=datetime.now(timezone.utc),
                decision_comment="Approbation initiale",
            )
            expiry_request = SupplierAccessRequest(
                supplier_id=expiry_supplier.id,
                supplier_asset_link_id=expiry_link.id,
                asset_id=expiry_asset.id,
                access_level="Standard",
                data_access=False,
                justification="Accès temporaire arrivé à échéance",
                scope="Maintenance du serveur",
                start_date=today - timedelta(days=30),
                end_date=today - timedelta(days=1),
                review_due_at=today - timedelta(days=1),
                status="Approuvé",
                requested_by_id=requester_id,
                decided_by_id=approver_id,
                decided_at=datetime.now(timezone.utc),
                decision_comment="Approbation initiale",
            )
            setup.add_all([review_request, expiry_request])
            await setup.commit()
            await setup.refresh(review_request)
            await setup.refresh(expiry_request)
            review_request_id = str(review_request.id)
            expiry_request_id = str(expiry_request.id)

        app = FastAPI()
        app.include_router(suppliers_endpoint.router, prefix="/api/v1")

        async def override_db():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        operator_token = create_access_token(
            subject=operator.email, role="admin", auth_version=1
        )
        headers = {"Authorization": f"Bearer {operator_token}"}
        review_supplier_id = str(review_supplier.id)
        expiry_supplier_id = str(expiry_supplier.id)

        with TestClient(app) as client:
            reviewed = client.post(
                f"/api/v1/suppliers/{review_supplier_id}/access-requests/{review_request_id}/reviews",
                headers=headers,
                json={
                    "outcome": "Maintenue",
                    "comment": "Accès toujours justifié et contrôlé",
                    "next_review_at": (date.today() + timedelta(days=7)).isoformat(),
                },
            )
            assert reviewed.status_code == 201, reviewed.text
            review_id = reviewed.json()["id"]
            assert reviewed.json()["outcome"] == "Maintenue"

            expired = client.post(
                f"/api/v1/suppliers/{expiry_supplier_id}/access-requests/{expiry_request_id}/expire",
                headers=headers,
            )
            assert expired.status_code == 200, expired.text
            assert expired.json()["status"] == "Expiré"

        async with sessions() as verify:
            persisted_review = await verify.get(SupplierAccessReview, review_id)
            persisted_review_request = await verify.get(
                SupplierAccessRequest, review_request_id
            )
            persisted_expiry_request = await verify.get(
                SupplierAccessRequest, expiry_request_id
            )
            audit_actions = (
                await verify.execute(
                    select(AuditOutbox.payload["action"].astext).where(
                        AuditOutbox.payload["resource_id"].astext.in_(
                            [review_id, expiry_request_id]
                        )
                    )
                )
            ).scalars().all()
            assert persisted_review.outcome == "Maintenue"
            assert persisted_review.reviewed_by_id == operator_id
            assert persisted_review_request.review_due_at == date.today() + timedelta(days=7)
            assert persisted_expiry_request.status == "Expiré"
            assert "REVIEW_SUPPLIER_ACCESS" in audit_actions
            assert "EXPIRE_SUPPLIER_ACCESS" in audit_actions
    finally:
        async with sessions() as cleanup:
            resource_ids = [
                item for item in (review_id, expiry_request_id) if item is not None
            ]
            if resource_ids:
                await cleanup.execute(
                    delete(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext.in_(resource_ids)
                    )
                )
            if review_id is not None:
                await cleanup.execute(
                    delete(SupplierAccessReview).where(
                        SupplierAccessReview.id == review_id
                    )
                )
            for request_id in (review_request_id, expiry_request_id):
                if request_id is not None:
                    await cleanup.execute(
                        delete(SupplierAccessRequest).where(
                            SupplierAccessRequest.id == request_id
                        )
                    )
            for link in (review_link, expiry_link):
                if link is not None:
                    await cleanup.execute(
                        delete(SupplierAssetLink).where(SupplierAssetLink.id == link.id)
                    )
            await cleanup.execute(
                delete(Asset).where(Asset.id.in_([review_asset.id, expiry_asset.id]))
            )
            await cleanup.execute(
                delete(Supplier).where(
                    Supplier.id.in_([review_supplier.id, expiry_supplier.id])
                )
            )
            await cleanup.execute(
                delete(User).where(
                    User.id.in_([requester_id, approver_id, operator_id])
                )
            )
            await cleanup.commit()
        await engine.dispose()
