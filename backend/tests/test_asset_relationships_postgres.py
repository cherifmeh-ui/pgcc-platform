"""PostgreSQL concurrency coverage for asset dependency graph mutations."""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints.assets import (
    AssetRiskLinkCreate, AssetUpdate, RelationshipCreate, create_asset_relationship,
    link_asset_to_risk, retire_asset, update_asset,
)
from app.models.action_item import ActionItem  # register Risk.actions mapper target before ORM use
from app.api.v1.endpoints.risks import delete_risk
from app.models.asset import Asset, AssetRelationship, AssetRiskLink
from app.models.audit_outbox import AuditOutbox
from app.models.risk import Risk

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")


def _request():
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/phase0-test",
        "headers": [(b"user-agent", b"phase0-postgres-test")],
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
                        request=_request(),
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
                        request=_request(),
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
                        request=_request(),
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

@pytest.mark.asyncio
async def test_asset_relationship_history_survives_retirement_and_reactivation():
    """Retirement preserves existing edges; reactivation allows new edges again."""
    engine = create_async_engine(DATABASE_URL, pool_size=4, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    asset_a_id, asset_b_id, asset_c_id = uuid4(), uuid4(), uuid4()
    user = MagicMock(email="phase1-relationship-lifecycle@example.invalid")
    relationship_ids = []
    try:
        async with sessions() as setup:
            setup.add_all([
                Asset(
                    id=asset_a_id, reference=f"REL-LIFE-A-{asset_a_id.hex[:8]}",
                    name="Relationship lifecycle A", asset_type="hardware",
                    lifecycle_status="Actif",
                ),
                Asset(
                    id=asset_b_id, reference=f"REL-LIFE-B-{asset_b_id.hex[:8]}",
                    name="Relationship lifecycle B", asset_type="hardware",
                    lifecycle_status="Actif",
                ),
                Asset(
                    id=asset_c_id, reference=f"REL-LIFE-C-{asset_c_id.hex[:8]}",
                    name="Relationship lifecycle C", asset_type="hardware",
                    lifecycle_status="Actif",
                ),
            ])
            await setup.commit()

        async with sessions() as db:
            first = await create_asset_relationship(
                asset_id=asset_a_id,
                data=RelationshipCreate(
                    target_asset_id=asset_b_id,
                    relationship_type="supports",
                    description="Historical relationship retained after retirement",
                ),
                request=_request(),
                db=db,
                current_user=user,
            )
            relationship_ids.append(first.id)

        async with sessions() as db:
            await retire_asset(
                asset_id=asset_a_id, request=_request(), db=db, current_user=user,
            )

        async with sessions() as verify:
            historical = (
                await verify.execute(
                    select(AssetRelationship).where(
                        AssetRelationship.source_asset_id == asset_a_id,
                        AssetRelationship.target_asset_id == asset_b_id,
                    )
                )
            ).scalars().all()
            assert len(historical) == 1
            relationship_ids.extend(item.id for item in historical)

        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await create_asset_relationship(
                    asset_id=asset_a_id,
                    data=RelationshipCreate(
                        target_asset_id=asset_c_id,
                        relationship_type="supports",
                    ),
                    request=_request(),
                    db=db,
                    current_user=user,
                )
            assert exc.value.status_code == 409

        async with sessions() as db:
            await update_asset(
                asset_id=asset_a_id,
                data=AssetUpdate(lifecycle_status="Actif"),
                request=_request(),
                db=db,
                current_user=user,
            )

        async with sessions() as db:
            second = await create_asset_relationship(
                asset_id=asset_a_id,
                data=RelationshipCreate(
                    target_asset_id=asset_c_id,
                    relationship_type="supports",
                    description="New relationship after reactivation",
                ),
                request=_request(),
                db=db,
                current_user=user,
            )
            relationship_ids.append(second.id)

        async with sessions() as verify:
            persisted = await verify.get(Asset, asset_a_id)
            edges = (
                await verify.execute(
                    select(AssetRelationship).where(
                        AssetRelationship.source_asset_id == asset_a_id
                    )
                )
            ).scalars().all()
            actions = (
                await verify.execute(
                    select(AuditOutbox.payload["action"].astext).where(
                        AuditOutbox.payload["resource_id"].astext.in_(
                            [str(asset_a_id), *[str(value) for value in relationship_ids]]
                        )
                    )
                )
            ).scalars().all()
            assert persisted.lifecycle_status == "Actif"
            assert persisted.retired_at is None
            assert {
                (edge.source_asset_id, edge.target_asset_id) for edge in edges
            } == {(asset_a_id, asset_b_id), (asset_a_id, asset_c_id)}
            assert "RETIRE" in actions
            assert "REACTIVATE" in actions
            assert actions.count("CREATE_RELATIONSHIP") == 2
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext.in_(
                        [str(asset_a_id), str(asset_b_id), str(asset_c_id),
                         *[str(value) for value in relationship_ids]]
                    )
                )
            )
            await cleanup.execute(
                delete(AssetRelationship).where(
                    or_(
                        AssetRelationship.source_asset_id.in_([asset_a_id, asset_b_id, asset_c_id]),
                        AssetRelationship.target_asset_id.in_([asset_a_id, asset_b_id, asset_c_id]),
                    )
                )
            )
            await cleanup.execute(
                delete(Asset).where(Asset.id.in_([asset_a_id, asset_b_id, asset_c_id]))
            )
            await cleanup.commit()
        await engine.dispose()
