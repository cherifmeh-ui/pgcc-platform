"""PostgreSQL concurrency coverage for asset dependency graph mutations."""
from __future__ import annotations

import asyncio
import os
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import delete, event, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.endpoints.assets import (
    AssetRiskLinkCreate, AssetUpdate, RelationshipCreate, create_asset_relationship,
    get_asset_dependency_graph, get_asset_impact, link_asset_to_risk, retire_asset, update_asset,
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


@pytest.mark.asyncio
async def test_concurrent_three_edge_dependency_cycle_is_rejected(monkeypatch):
    """Concurrent edges forming a three-node cycle must serialize to a DAG."""
    engine = create_async_engine(DATABASE_URL, pool_size=6, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    assets = [
        Asset(
            reference=f"REL-TRI-{index}-{uuid4().hex[:10]}",
            name=f"Phase 1 concurrent cycle asset {index}",
            asset_type="hardware",
            lifecycle_status="Actif",
        )
        for index in range(3)
    ]
    monkeypatch.setattr("app.api.v1.endpoints.assets.log_action", AsyncMock())
    asset_ids = []
    relationship_ids = []
    try:
        async with sessions() as setup:
            setup.add_all(assets)
            await setup.commit()
            for asset in assets:
                await setup.refresh(asset)
                asset_ids.append(asset.id)

        candidate_edges = [
            (asset_ids[0], asset_ids[1]),
            (asset_ids[1], asset_ids[2]),
            (asset_ids[2], asset_ids[0]),
        ]

        async def create_edge(source_id, target_id):
            async with sessions() as db:
                try:
                    relationship = await create_asset_relationship(
                        asset_id=source_id,
                        data=RelationshipCreate(
                            target_asset_id=target_id,
                            relationship_type="depends_on",
                        ),
                        request=_request(),
                        db=db,
                        current_user=MagicMock(email="phase1-cycle@example.invalid"),
                    )
                    return (201, relationship.id)
                except HTTPException as exc:
                    return (exc.status_code, None)

        outcomes = await asyncio.gather(
            *(create_edge(source_id, target_id) for source_id, target_id in candidate_edges)
        )
        assert sorted(code for code, _ in outcomes) == [201, 201, 422]
        relationship_ids.extend(
            relationship_id for code, relationship_id in outcomes
            if code == 201 and relationship_id is not None
        )

        async with sessions() as verify:
            persisted = (
                await verify.execute(
                    select(AssetRelationship).where(
                        AssetRelationship.relationship_type == "depends_on",
                        AssetRelationship.source_asset_id.in_(asset_ids),
                        AssetRelationship.target_asset_id.in_(asset_ids),
                    )
                )
            ).scalars().all()
            assert len(persisted) == 2
            assert {
                (edge.source_asset_id, edge.target_asset_id) for edge in persisted
            } == {
                edge for (code, relationship_id), edge in zip(outcomes, candidate_edges)
                if code == 201
            }
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext.in_(
                        [str(value) for value in relationship_ids]
                    )
                )
            )
            await cleanup.execute(
                delete(AssetRelationship).where(
                    or_(
                        AssetRelationship.source_asset_id.in_(asset_ids),
                        AssetRelationship.target_asset_id.in_(asset_ids),
                    )
                )
            )
            await cleanup.execute(delete(Asset).where(Asset.id.in_(asset_ids)))
            await cleanup.commit()
        await engine.dispose()



@pytest.mark.asyncio
async def test_asset_impact_includes_source_and_transitive_risks_once(monkeypatch):
    """Risk synthesis includes the source asset and deduplicates shared risk links."""
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    source, dependent, downstream = [
        Asset(
            reference=f"IMPACT-{label}-{uuid4().hex[:10]}",
            name=f"Phase 1 impact {label}",
            asset_type="hardware",
            lifecycle_status="Actif",
        )
        for label in ("SOURCE", "DEPENDENT", "DOWNSTREAM")
    ]
    shared_risk = Risk(
        ref=f"IMPACT-SHARED-{uuid4().hex[:10]}",
        title="Shared impact risk",
        impact=4,
        likelihood=5,
        risk_level=20,
        status="Ouvert",
    )
    source_only_risk = Risk(
        ref=f"IMPACT-SOURCE-{uuid4().hex[:10]}",
        title="Source-only impact risk",
        impact=3,
        likelihood=3,
        risk_level=9,
        status="En traitement",
    )

    try:
        async with sessions() as setup:
            setup.add_all([source, dependent, downstream, shared_risk, source_only_risk])
            await setup.flush()
            setup.add_all([
                AssetRelationship(
                    source_asset_id=dependent.id,
                    target_asset_id=source.id,
                    relationship_type="depends_on",
                ),
                AssetRelationship(
                    source_asset_id=downstream.id,
                    target_asset_id=dependent.id,
                    relationship_type="depends_on",
                ),
                AssetRiskLink(asset_id=source.id, risk_id=shared_risk.id),
                AssetRiskLink(asset_id=dependent.id, risk_id=shared_risk.id),
                AssetRiskLink(asset_id=source.id, risk_id=source_only_risk.id),
            ])
            await setup.commit()
            await setup.refresh(source)

        async with sessions() as db:
            result = await get_asset_impact(
                asset_id=source.id,
                db=db,
                current_user=MagicMock(role="executive"),
            )

        assert result["total_impacted"] == 2
        assert [item["dependency_distance"] for item in result["impacted_assets"]] == [1, 2]
        assert {item["ref"] for item in result["source"]["linked_risks"]} == {
            shared_risk.ref, source_only_risk.ref,
        }
        assert result["risk_summary"]["total"] == 2
        assert result["risk_summary"]["unacceptable"] == 1
        assert result["risk_summary"]["moderate"] == 1
        assert result["risk_summary"]["by_status"] == {
            "Ouvert": 1, "En traitement": 1,
        }
        shared_dependent = next(
            item for item in result["impacted_assets"] if item["id"] == dependent.id
        )
        assert [risk["id"] for risk in shared_dependent["linked_risks"]] == [shared_risk.id]
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AssetRiskLink).where(
                    AssetRiskLink.asset_id.in_([source.id, dependent.id, downstream.id])
                )
            )
            await cleanup.execute(
                delete(AssetRelationship).where(
                    or_(
                        AssetRelationship.source_asset_id.in_([source.id, dependent.id, downstream.id]),
                        AssetRelationship.target_asset_id.in_([source.id, dependent.id, downstream.id]),
                    )
                )
            )
            await cleanup.execute(
                delete(Asset).where(Asset.id.in_([source.id, dependent.id, downstream.id]))
            )
            await cleanup.execute(
                delete(Risk).where(Risk.id.in_([shared_risk.id, source_only_risk.id]))
            )
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_asset_graph_query_count_is_constant_for_large_inventory():
    """The graph read model must not regress to per-node ORM lazy-load queries."""
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    assets = [
        Asset(
            reference=f"GRAPH-BENCH-{uuid4().hex[:12]}",
            name=f"Graph benchmark asset {index:04d}",
            asset_type="hardware",
            lifecycle_status="Actif",
        )
        for index in range(600)
    ]
    select_statements = []

    def count_selects(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement.lower())

    try:
        async with sessions() as setup:
            setup.add_all(assets)
            await setup.flush()
            setup.add_all([
                AssetRelationship(
                    source_asset_id=assets[index + 1].id,
                    target_asset_id=assets[index].id,
                    relationship_type="depends_on",
                )
                for index in range(len(assets) - 1)
            ])
            await setup.commit()

        event.listen(engine.sync_engine, "before_cursor_execute", count_selects)
        started = perf_counter()
        async with sessions() as db:
            result = await get_asset_dependency_graph(
                db=db,
                current_user=MagicMock(role="admin"),
            )
        elapsed_seconds = perf_counter() - started
        event.remove(engine.sync_engine, "before_cursor_execute", count_selects)

        assert result["node_count"] == 600
        assert result["edge_count"] == 599
        assert len(select_statements) == 2, (
            f"expected two set-based SELECTs, got {len(select_statements)} "
            f"in {elapsed_seconds:.3f}s"
        )
        assert all("assets.description" not in statement for statement in select_statements)
        assert all("assets.serial_number" not in statement for statement in select_statements)
    finally:
        try:
            event.remove(engine.sync_engine, "before_cursor_execute", count_selects)
        except Exception:
            pass
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AssetRelationship).where(
                    or_(
                        AssetRelationship.source_asset_id.in_([asset.id for asset in assets]),
                        AssetRelationship.target_asset_id.in_([asset.id for asset in assets]),
                    )
                )
            )
            await cleanup.execute(delete(Asset).where(Asset.id.in_([asset.id for asset in assets])))
            await cleanup.commit()
        await engine.dispose()
