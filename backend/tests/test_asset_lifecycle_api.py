from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.assets import retire_asset, unlink_asset_from_risk


ASSET_ID = UUID("00000000-0000-0000-0000-000000000001")
RISK_ID = UUID("00000000-0000-0000-0000-000000000002")


def _db_for_asset(asset, *, open_access=False, active_supplier_link=False):
    db = AsyncMock()
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = asset
    access_result = MagicMock()
    access_result.scalar_one_or_none.return_value = (
        UUID("00000000-0000-0000-0000-000000000099") if open_access else None
    )
    active_link_result = MagicMock()
    active_link_result.scalar_one_or_none.return_value = (
        UUID("00000000-0000-0000-0000-000000000098") if active_supplier_link else None
    )
    db.execute.side_effect = [asset_result, access_result, active_link_result]
    return db


@pytest.mark.asyncio
async def test_retire_asset_repairs_active_status_with_existing_retirement_marker(monkeypatch):
    retired_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asset = MagicMock(
        id=ASSET_ID, reference="AST-001", lifecycle_status="Actif",
        retired_at=retired_at,
    )
    db = _db_for_asset(asset)
    audit = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    await retire_asset(
        asset_id=ASSET_ID, request=MagicMock(), db=db,
        current_user=MagicMock(email="admin@example.test"),
    )

    assert asset.lifecycle_status == "Retiré"
    assert asset.retired_at == retired_at
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "RETIRE"


@pytest.mark.asyncio
async def test_retire_asset_sets_marker_and_rolls_back_if_audit_enqueue_fails(monkeypatch):
    asset = MagicMock(
        id=ASSET_ID, reference="AST-002", lifecycle_status="Actif",
        retired_at=None,
    )
    db = _db_for_asset(asset)
    audit = AsyncMock(side_effect=RuntimeError("outbox unavailable"))
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await retire_asset(
            asset_id=ASSET_ID, request=MagicMock(), db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert asset.lifecycle_status == "Retiré"
    assert asset.retired_at is not None
    db.flush.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_retire_asset_is_idempotent_when_status_and_marker_are_consistent(monkeypatch):
    asset = MagicMock(
        id=ASSET_ID, reference="AST-003", lifecycle_status="Décommissionné",
        retired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = _db_for_asset(asset)
    audit = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    await retire_asset(
        asset_id=ASSET_ID, request=MagicMock(), db=db,
        current_user=MagicMock(email="admin@example.test"),
    )

    audit.assert_not_awaited()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unlink_asset_risk_rolls_back_if_audit_enqueue_fails(monkeypatch):
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = ASSET_ID
    risk_result = MagicMock()
    risk_result.scalar_one_or_none.return_value = RISK_ID
    link = MagicMock(asset_id=ASSET_ID, risk_id=RISK_ID)
    link_result = MagicMock()
    link_result.scalar_one_or_none.return_value = link

    db = AsyncMock()
    db.execute.side_effect = [asset_result, risk_result, link_result]
    audit = AsyncMock(side_effect=RuntimeError("outbox unavailable"))
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await unlink_asset_from_risk(
            asset_id=ASSET_ID, risk_id=RISK_ID, request=MagicMock(), db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )

    db.delete.assert_awaited_once_with(link)
    db.flush.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_link_asset_risk_rolls_back_if_audit_enqueue_fails(monkeypatch):
    from app.api.v1.endpoints.assets import AssetRiskLinkCreate, link_asset_to_risk

    asset = MagicMock(
        id=ASSET_ID, reference="AST-004", lifecycle_status="Actif",
        retired_at=None,
    )
    risk = MagicMock(id=RISK_ID, ref="RISK-004")
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = asset
    risk_result = MagicMock()
    risk_result.scalar_one_or_none.return_value = risk

    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [asset_result, risk_result]
    audit = AsyncMock(side_effect=RuntimeError("outbox unavailable"))
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await link_asset_to_risk(
            asset_id=ASSET_ID,
            data=AssetRiskLinkCreate(risk_id=RISK_ID),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(role="admin", email="admin@example.test"),
        )

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_reactivation_clears_retirement_marker_and_has_explicit_audit(monkeypatch):
    from app.api.v1.endpoints.assets import AssetUpdate, update_asset

    retired_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asset = MagicMock(
        id=ASSET_ID,
        reference="AST-005",
        lifecycle_status="Retiré",
        retired_at=retired_at,
    )
    db = _db_for_asset(asset)
    audit = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    await update_asset(
        asset_id=ASSET_ID,
        data=AssetUpdate(lifecycle_status="Actif"),
        request=MagicMock(),
        db=db,
        current_user=MagicMock(email="admin@example.test"),
    )

    assert asset.lifecycle_status == "Actif"
    assert asset.retired_at is None
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "REACTIVATE"
    assert "AST-005" in audit.await_args.kwargs["details"]


@pytest.mark.asyncio
async def test_reactivation_rolls_back_when_audit_enqueue_fails(monkeypatch):
    from app.api.v1.endpoints.assets import AssetUpdate, update_asset

    asset = MagicMock(
        id=ASSET_ID,
        reference="AST-006",
        lifecycle_status="Décommissionné",
        retired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = _db_for_asset(asset)
    audit = AsyncMock(side_effect=RuntimeError("outbox unavailable"))
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await update_asset(
            asset_id=ASSET_ID,
            data=AssetUpdate(lifecycle_status="Actif"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert asset.lifecycle_status == "Actif"
    assert asset.retired_at is None
    db.flush.assert_awaited_once()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

@pytest.mark.asyncio
async def test_retire_asset_is_blocked_while_supplier_access_is_open(monkeypatch):
    asset = MagicMock(
        id=ASSET_ID, reference="AST-007", lifecycle_status="Actif",
        retired_at=None,
    )
    db = _db_for_asset(asset, open_access=True)
    audit = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    with pytest.raises(HTTPException) as exc:
        await retire_asset(
            asset_id=ASSET_ID, request=MagicMock(), db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert exc.value.status_code == 409
    assert "autorisation d'accès fournisseur" in exc.value.detail
    assert asset.lifecycle_status == "Actif"
    assert asset.retired_at is None
    audit.assert_not_awaited()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_retire_asset_proceeds_when_no_supplier_access_is_open(monkeypatch):
    asset = MagicMock(
        id=ASSET_ID, reference="AST-008", lifecycle_status="Actif",
        retired_at=None,
    )
    db = _db_for_asset(asset, open_access=False)
    audit = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    await retire_asset(
        asset_id=ASSET_ID, request=MagicMock(), db=db,
        current_user=MagicMock(email="admin@example.test"),
    )

    assert asset.lifecycle_status == "Retiré"
    assert asset.retired_at is not None
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    audit.assert_awaited_once()



@pytest.mark.asyncio
async def test_retire_asset_is_blocked_while_supplier_asset_link_is_active(monkeypatch):
    asset = MagicMock(
        id=ASSET_ID, reference="AST-009", lifecycle_status="Actif",
        retired_at=None,
    )
    db = _db_for_asset(asset, active_supplier_link=True)
    audit = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.assets.enqueue_audit_event", audit)

    with pytest.raises(HTTPException) as exc:
        await retire_asset(
            asset_id=ASSET_ID, request=MagicMock(), db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert exc.value.status_code == 409
    assert "relation fournisseur-actif" in exc.value.detail
    assert asset.lifecycle_status == "Actif"
    assert asset.retired_at is None
    audit.assert_not_awaited()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()
