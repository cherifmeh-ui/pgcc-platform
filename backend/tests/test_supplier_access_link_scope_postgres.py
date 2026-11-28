"""PostgreSQL enforcement of supplier access request link identity."""
from __future__ import annotations

import os
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.action_item import ActionItem  # register Risk.actions mapper target
from app.models.asset import Asset
from app.models.supplier import Supplier, SupplierAccessRequest, SupplierAssetLink
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_access_request_must_match_supplier_and_asset_of_link():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid4()
    user = User(
        id=token,
        email=f"phase0-link-scope-{token.hex}@example.invalid",
        full_name="Phase 0 supplier link scope test",
        role="viewer",
        password_hash="not-used",
        must_change_password=False,
        is_active=True,
        mfa_enabled=True,
    )
    supplier = Supplier(
        code=f"PH0-LS-{token.hex[:10]}",
        legal_name="Phase 0 link scope supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    other_supplier = Supplier(
        code=f"PH0-LO-{token.hex[:10]}",
        legal_name="Phase 0 other link scope supplier",
        status="Approuvé",
        criticality="Moyenne",
        dependency_level="Moyenne",
    )
    asset = Asset(
        reference=f"PH0-LS-{token.hex[:10]}",
        name="Phase 0 linked asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    other_asset = Asset(
        reference=f"PH0-LO-{token.hex[:10]}",
        name="Phase 0 other asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    link = None
    today = date.today()
    try:
        async with sessions() as db:
            db.add_all([user, supplier, other_supplier, asset, other_asset])
            await db.commit()
            link = SupplierAssetLink(
                supplier_id=supplier.id,
                asset_id=asset.id,
                relationship_type="Maintient",
                access_level="Standard",
                data_access=False,
                status="Actif",
                created_by_id=user.id,
            )
            db.add(link)
            await db.commit()
            await db.refresh(link)

        for mismatch in ("supplier", "asset"):
            async with sessions() as db:
                request = SupplierAccessRequest(
                    supplier_id=other_supplier.id if mismatch == "supplier" else supplier.id,
                    supplier_asset_link_id=link.id,
                    asset_id=other_asset.id if mismatch == "asset" else asset.id,
                    access_level="Standard",
                    data_access=False,
                    justification="Test d'intégrité relationnelle",
                    scope="Test PostgreSQL",
                    start_date=today,
                    end_date=today + timedelta(days=30),
                    review_due_at=today + timedelta(days=15),
                    status="Demandé",
                    requested_by_id=user.id,
                )
                db.add(request)
                with pytest.raises(IntegrityError):
                    await db.flush()
                await db.rollback()

        # A request whose three identifiers match the link remains valid.
        async with sessions() as db:
            db.add(SupplierAccessRequest(
                supplier_id=supplier.id,
                supplier_asset_link_id=link.id,
                asset_id=asset.id,
                access_level="Standard",
                data_access=False,
                justification="Demande valide de test",
                scope="Test PostgreSQL",
                start_date=today,
                end_date=today + timedelta(days=30),
                review_due_at=today + timedelta(days=15),
                status="Demandé",
                requested_by_id=user.id,
            ))
            await db.commit()
    finally:
        async with sessions() as db:
            if link is not None:
                await db.execute(delete(SupplierAccessRequest).where(
                    SupplierAccessRequest.supplier_asset_link_id == link.id
                ))
                await db.execute(delete(SupplierAssetLink).where(
                    SupplierAssetLink.id == link.id
                ))
            await db.execute(delete(Asset).where(Asset.id.in_([asset.id, other_asset.id])))
            await db.execute(delete(Supplier).where(
                Supplier.id.in_([supplier.id, other_supplier.id])
            ))
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()
        await engine.dispose()
