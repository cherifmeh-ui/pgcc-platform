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


@pytest.mark.asyncio
async def test_asset_risk_link_creation_requires_risk_update_permission():
    from app.api.v1.endpoints.assets import AssetRiskLinkCreate, link_asset_to_risk
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await link_asset_to_risk(
            asset_id=ASSET_ID, data=AssetRiskLinkCreate(risk_id=RISK_ID),
            request=MagicMock(), db=db,
            current_user=MagicMock(role="auditor", email="auditor@example.test"),
        )
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_risk_unlink_requires_risk_update_permission():
    from app.api.v1.endpoints.assets import unlink_asset_from_risk
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await unlink_asset_from_risk(
            asset_id=ASSET_ID, risk_id=RISK_ID, request=MagicMock(), db=db,
            current_user=MagicMock(role="auditor", email="auditor@example.test"),
        )
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_risk_deletion_is_blocked_when_asset_links_exist():
    from app.api.v1.endpoints.risks import delete_risk

    db = AsyncMock()
    risk = MagicMock(ref="RISK-001", title="Risque critique")
    risk.id = RISK_ID
    risk_result = MagicMock()
    risk_result.scalar_one_or_none.return_value = risk
    action_count = MagicMock()
    action_count.scalar_one.return_value = 0
    asset_link_count = MagicMock()
    asset_link_count.scalar_one.return_value = 1
    db.execute.side_effect = [risk_result, action_count, asset_link_count]

    with pytest.raises(HTTPException) as exc:
        await delete_risk(
            risk_id=RISK_ID, request=MagicMock(), db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )
    assert exc.value.status_code == 409
    assert "associé" in exc.value.detail
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()

def test_asset_risk_link_eligibility_rejects_retired_lifecycle():
    from app.api.v1.endpoints.assets import _asset_allows_risk_link
    from datetime import datetime, timezone
    assert not _asset_allows_risk_link("Retiré", None)
    assert not _asset_allows_risk_link("Décommissionné", None)
    assert not _asset_allows_risk_link("Actif", datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_asset_risk_link_eligibility_allows_active_assets():
    from app.api.v1.endpoints.assets import _asset_allows_risk_link
    assert _asset_allows_risk_link("Actif", None)
    assert _asset_allows_risk_link("En maintenance", None)
    assert _asset_allows_risk_link("En projet", None)

@pytest.mark.asyncio
async def test_asset_risk_unlink_returns_404_when_asset_missing():
    from app.api.v1.endpoints.assets import unlink_asset_from_risk
    db = AsyncMock()
    missing = MagicMock()
    missing.scalar_one_or_none.return_value = None
    db.execute.return_value = missing
    with pytest.raises(HTTPException) as exc:
        await unlink_asset_from_risk(
            asset_id=ASSET_ID, risk_id=RISK_ID, request=MagicMock(), db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )
    assert exc.value.status_code == 404
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_risk_unlink_returns_404_when_risk_missing():
    from app.api.v1.endpoints.assets import unlink_asset_from_risk
    db = AsyncMock()
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = ASSET_ID
    missing_risk = MagicMock()
    missing_risk.scalar_one_or_none.return_value = None
    db.execute.side_effect = [asset_result, missing_risk]
    with pytest.raises(HTTPException) as exc:
        await unlink_asset_from_risk(
            asset_id=ASSET_ID, risk_id=RISK_ID, request=MagicMock(), db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )
    assert exc.value.status_code == 404
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_asset_risk_link_creation_rejects_retired_asset():
    from app.api.v1.endpoints.assets import AssetRiskLinkCreate, link_asset_to_risk
    asset = MagicMock(id=ASSET_ID, retired_at=None, lifecycle_status="Retiré", reference="AST-001")
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = asset
    db = AsyncMock()
    db.execute.return_value = asset_result
    with pytest.raises(HTTPException) as exc:
        await link_asset_to_risk(
            asset_id=ASSET_ID, data=AssetRiskLinkCreate(risk_id=RISK_ID),
            request=MagicMock(), db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )
    assert exc.value.status_code == 409
    assert db.execute.await_count == 1
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_risk_link_creation_rejects_retired_marker():
    from datetime import datetime, timezone
    from app.api.v1.endpoints.assets import AssetRiskLinkCreate, link_asset_to_risk
    asset = MagicMock(
        id=ASSET_ID, retired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        lifecycle_status="Actif", reference="AST-001",
    )
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = asset
    db = AsyncMock()
    db.execute.return_value = asset_result
    with pytest.raises(HTTPException) as exc:
        await link_asset_to_risk(
            asset_id=ASSET_ID, data=AssetRiskLinkCreate(risk_id=RISK_ID),
            request=MagicMock(), db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )
    assert exc.value.status_code == 409
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
