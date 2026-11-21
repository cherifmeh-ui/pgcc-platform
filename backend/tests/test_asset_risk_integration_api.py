from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.assets import list_asset_risk_links
from app.api.v1.endpoints.risks import list_risk_assets


ASSET_ID = UUID("00000000-0000-0000-0000-000000000001")
RISK_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_asset_risk_link_listing_requires_risk_read_permission():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await list_asset_risk_links(
            asset_id=ASSET_ID, db=db, current_user=MagicMock(role="limited")
        )
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_risk_asset_listing_requires_asset_read_permission():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await list_risk_assets(
            risk_id=RISK_ID, db=db, current_user=MagicMock(role="viewer")
        )
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_risk_asset_listing_returns_linked_asset_context_for_auditor():
    db = AsyncMock()
    risk_result = MagicMock()
    risk_result.scalar_one_or_none.return_value = RISK_ID
    rows_result = MagicMock()
    asset = MagicMock()
    asset.id = ASSET_ID
    asset.reference = "AST-001"
    asset.name = "Serveur applicatif"
    asset.asset_type = "hardware"
    asset.criticality = "Critique"
    asset.lifecycle_status = "Actif"
    rows_result.all.return_value = [(asset, "Héberge l'application critique")]
    db.execute.side_effect = [risk_result, rows_result]

    response = await list_risk_assets(
        risk_id=RISK_ID, db=db, current_user=MagicMock(role="auditor")
    )

    assert len(response) == 1
    assert response[0].id == ASSET_ID
    assert response[0].reference == "AST-001"
    assert response[0].relationship_context == "Héberge l'application critique"
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_risk_asset_listing_returns_404_when_risk_does_not_exist():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await list_risk_assets(
            risk_id=RISK_ID, db=db, current_user=MagicMock(role="auditor")
        )
    assert exc.value.status_code == 404
    assert db.execute.await_count == 1
