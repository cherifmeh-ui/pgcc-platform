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

from app.api.v1.endpoints.assets import (
    AssetRiskLinkCreate, RelationshipCreate, create_asset_relationship,
    link_asset_to_risk,
)
from app.models.action_item import ActionItem  # register Risk.actions mapper target before ORM use
from app.api.v1.endpoints.risks import delete_risk
from app.models.asset import Asset, AssetRelationship, AssetRiskLink
from app.models.risk import Risk

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


@pytest.mark.asyncio
async def test_concurrent_asset_risk_link_and_risk_delete_are_serialized(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset = Asset(
        reference=f"RISK-LINK-{uuid4().hex[:12]}",
        name="Phase 0 risk-link concurrency asset",
        asset_type="hardware",
        lifecycle_status="Actif",
    )
    risk = Risk(
        ref=f"RISK-LINK-{uuid4().hex[:12]}",
        title="Phase 0 risk-link concurrency risk",
        impact=3,
        likelihood=3,
        risk_level=9,
        status="Ouvert",
    )
    monkeypatch.setattr("app.api.v1.endpoints.assets.log_action", AsyncMock())
    monkeypatch.setattr("app.api.v1.endpoints.risks.log_action", AsyncMock())

    try:
        async with sessions() as setup:
            setup.add_all([asset, risk])
            await setup.commit()
            await setup.refresh(asset)
            await setup.refresh(risk)

        async def create_link():
            async with sessions() as db:
                try:
                    await link_asset_to_risk(
                        asset_id=asset.id,
                        data=AssetRiskLinkCreate(risk_id=risk.id),
                        request=MagicMock(),
                        db=db,
                        current_user=MagicMock(role="admin", email="phase0-test@example.invalid"),
                    )
                    return ("link", 201)
                except HTTPException as exc:
                    return ("link", exc.status_code)

        async def remove_risk():
            async with sessions() as db:
                try:
                    await delete_risk(
                        risk_id=risk.id,
                        request=MagicMock(),
                        db=db,
                        current_user=MagicMock(role="admin", email="phase0-test@example.invalid"),
                    )
                    return ("delete", 200)
                except HTTPException as exc:
                    return ("delete", exc.status_code)

        outcomes = await asyncio.gather(create_link(), remove_risk())
        outcome_codes = {name: code for name, code in outcomes}
        assert (
            outcome_codes == {"link": 201, "delete": 409}
            or outcome_codes == {"link": 404, "delete": 200}
        )

        async with sessions() as verify:
            risk_exists = (await verify.execute(
                select(Risk.id).where(Risk.id == risk.id)
            )).scalar_one_or_none() is not None
            link_exists = (await verify.execute(
                select(AssetRiskLink.id).where(
                    AssetRiskLink.asset_id == asset.id,
                    AssetRiskLink.risk_id == risk.id,
                )
            )).scalar_one_or_none() is not None
            assert risk_exists == link_exists
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(AssetRiskLink).where(
                AssetRiskLink.risk_id == risk.id
            ))
            await cleanup.execute(delete(Risk).where(Risk.id == risk.id))
            await cleanup.execute(delete(Asset).where(Asset.id == asset.id))
            await cleanup.commit()
        await engine.dispose()
