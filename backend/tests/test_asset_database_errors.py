from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.assets import AssetCreate, AssetUpdate, create_asset, update_asset


ASSET_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_create_asset_maps_integrity_error_to_conflict():
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("duplicate")))
    db.rollback = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await create_asset(
            data=AssetCreate(reference="AST-001", name="Serveur"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert exc.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_asset_propagates_unexpected_database_error():
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock(side_effect=RuntimeError("database connection lost"))
    db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="database connection lost"):
        await create_asset(
            data=AssetCreate(reference="AST-002", name="Serveur"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_asset_propagates_unexpected_database_error():
    db = MagicMock()
    asset = MagicMock(id=ASSET_ID, retired_at=None, lifecycle_status="Actif")
    result = MagicMock()
    result.scalar_one_or_none.return_value = asset
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock(side_effect=RuntimeError("database unavailable"))
    db.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="database unavailable"):
        await update_asset(
            asset_id=ASSET_ID,
            data=AssetUpdate(name="Serveur modifié"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    db.rollback.assert_awaited_once()
