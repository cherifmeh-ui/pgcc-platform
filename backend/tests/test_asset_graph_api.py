from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.api.v1.endpoints.assets import get_asset_dependency_graph


A = UUID("00000000-0000-0000-0000-000000000001")
B = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_graph_returns_active_assets_and_relationships():
    db = AsyncMock()
    asset_result = MagicMock()
    asset_result.scalars.return_value.all.return_value = [
        MagicMock(id=A, reference="AST-001", name="Serveur", asset_type="hardware", criticality="Critique", direction="DI"),
        MagicMock(id=B, reference="AST-002", name="Application", asset_type="application", criticality="Élevée", direction="DI"),
    ]
    relation_result = MagicMock()
    relation_result.scalars.return_value.all.return_value = [
        MagicMock(id=UUID("00000000-0000-0000-0000-000000000004"), source_asset_id=B, target_asset_id=A, relationship_type="depends_on", description="Application hébergée"),
    ]
    db.execute.side_effect = [asset_result, relation_result]

    result = await get_asset_dependency_graph(db=db, current_user=MagicMock(role="admin"))

    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert {node["id"] for node in result["nodes"]} == {A, B}
    assert result["edges"][0]["source"] == B
    assert result["edges"][0]["target"] == A
    assert db.execute.await_count == 2
    asset_statement = str(db.execute.await_args_list[0].args[0]).lower()
    assert "assets.reference" in asset_statement
    assert "assets.lifecycle_status" in asset_statement
    assert "assets.serial_number" not in asset_statement
    assert "assets.description" not in asset_statement

    relation_statement = str(db.execute.await_args_list[1].args[0]).lower()
    assert "asset_relationships.relationship_type" in relation_statement
    assert "asset_relationships.source_asset_id in (select" in relation_statement
    assert "asset_relationships.created_at" not in relation_statement
    assert "asset_relationships.description" in relation_statement
    assert "asset_relationships.target_asset_id in (select" in relation_statement
    assert "assets.retired_at is null" in relation_statement


@pytest.mark.asyncio
async def test_graph_returns_empty_graph_when_inventory_empty():
    db = AsyncMock()
    asset_result = MagicMock()
    asset_result.scalars.return_value.all.return_value = []
    relation_result = MagicMock()
    relation_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [asset_result, relation_result]

    result = await get_asset_dependency_graph(db=db, current_user=MagicMock(role="admin"))

    assert result == {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}


@pytest.mark.asyncio
async def test_impact_rejects_retired_source_before_loading_dependency_graph():
    from fastapi import HTTPException
    from app.api.v1.endpoints.assets import get_asset_impact

    retired = MagicMock(
        id=A, reference="AST-RETIRED", name="Actif retiré",
        lifecycle_status="Retiré", retired_at=None,
    )
    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = retired
    db = AsyncMock()
    db.execute.return_value = source_result

    with pytest.raises(HTTPException) as exc:
        await get_asset_impact(
            asset_id=A, db=db, current_user=MagicMock(role="viewer"),
        )

    assert exc.value.status_code == 404
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_impact_excludes_retired_assets_from_dependency_edges():
    from app.api.v1.endpoints.assets import get_asset_impact

    source = MagicMock(
        id=A, reference="AST-ACTIVE", name="Actif source",
        lifecycle_status="Actif", retired_at=None,
    )
    source_result = MagicMock()
    source_result.scalar_one_or_none.return_value = source
    relation_result = MagicMock()
    relation_result.all.return_value = []
    db = AsyncMock()
    db.execute.side_effect = [source_result, relation_result]

    result = await get_asset_impact(
        asset_id=A, db=db, current_user=MagicMock(role="viewer"),
    )

    assert result["source"]["id"] == A
    assert result["impacted_assets"] == []
    assert result["total_impacted"] == 0
    assert result["supplier_access_available"] is False
    assert db.execute.await_count == 2

    relation_sql = str(db.execute.await_args_list[1].args[0]).lower()
    assert "asset_relationships.relationship_type =" in relation_sql
    assert "depends_on" in str(db.execute.await_args_list[1].args[0].compile().params.values())
    assert relation_sql.count("retired_at is null") == 2
    bound_values = str(db.execute.await_args_list[1].args[0].compile().params.values())
    assert "Retiré" in bound_values
    assert "Décommissionné" in bound_values
