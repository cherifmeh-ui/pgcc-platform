"""PostgreSQL concurrency coverage for asset dependency graph mutations."""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints.assets import RelationshipCreate, create_asset_relationship
from app.models.asset import Asset, AssetRelationship

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_concurrent_opposing_dependency_edges_allow_only_one_direction(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_a = Asset(
        reference=f"REL-A-{uuid4().hex[:12]}",
        name="Phase 0 dependency source A",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    asset_b = Asset(
        reference=f"REL-B-{uuid4().hex[:12]}",
        name="Phase 0 dependency source B",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.assets.log_action",
        AsyncMock(),
    )

    try:
        async with sessions() as setup:
            setup.add_all([asset_a, asset_b])
            await setup.commit()
            await setup.refresh(asset_a)
            await setup.refresh(asset_b)

        async def create_edge(source_id, target_id):
            async with sessions() as db:
                try:
                    await create_asset_relationship(
                        asset_id=source_id,
                        data=RelationshipCreate(
                            target_asset_id=target_id,
                            relationship_type="depends_on",
                        ),
                        request=MagicMock(),
                        db=db,
                        current_user=MagicMock(email="phase0-test@example.invalid"),
                    )
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        results = await asyncio.gather(
            create_edge(asset_a.id, asset_b.id),
            create_edge(asset_b.id, asset_a.id),
        )
        assert sorted(results) == [201, 422]

        async with sessions() as verify:
            edges = (await verify.execute(
                select(AssetRelationship).where(
                    AssetRelationship.relationship_type == "depends_on",
                    or_(
                        AssetRelationship.source_asset_id.in_([asset_a.id, asset_b.id]),
                        AssetRelationship.target_asset_id.in_([asset_a.id, asset_b.id]),
                    ),
                )
            )).scalars().all()
            assert len(edges) == 1
            assert {
                (edges[0].source_asset_id, edges[0].target_asset_id)
            } in (
                {(asset_a.id, asset_b.id)},
                {(asset_b.id, asset_a.id)},
            )
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(AssetRelationship).where(
                or_(
                    AssetRelationship.source_asset_id.in_([asset_a.id, asset_b.id]),
                    AssetRelationship.target_asset_id.in_([asset_a.id, asset_b.id]),
                )
            ))
            await cleanup.execute(delete(Asset).where(Asset.id.in_([asset_a.id, asset_b.id])))
            await cleanup.commit()
        await engine.dispose()
