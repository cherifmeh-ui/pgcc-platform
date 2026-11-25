"""PostgreSQL transaction tests for asset retirement and audit consistency."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.assets import retire_asset
from app.models.asset import Asset
from app.models.audit_outbox import AuditOutbox

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
