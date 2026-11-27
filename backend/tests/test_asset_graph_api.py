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
    relation_statement = str(db.execute.await_args_list[1].args[0]).lower()
    assert "asset_relationships.source_asset_id in (select" in relation_statement
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
