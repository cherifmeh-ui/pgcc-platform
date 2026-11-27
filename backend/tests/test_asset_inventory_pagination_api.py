from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.assets import list_assets_page


@pytest.mark.asyncio
async def test_asset_inventory_page_returns_total_and_page_metadata():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 31
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = ["asset-1", "asset-2"]
    db.execute.side_effect = [count_result, item_result]

    response = await list_assets_page(
        q="serveur",
        asset_type="hardware",
        criticality=None,
        lifecycle_status=None,
        direction="DI",
        owner="admin",
        classification=None,
        location=None,
        include_retired=False,
        page=2,
        page_size=10,
        db=db,
        current_user=MagicMock(role="admin"),
    )

    assert response["items"] == ["asset-1", "asset-2"]
    assert response["total"] == 31
    assert response["page"] == 2
    assert response["page_size"] == 10
    assert response["pages"] == 4
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_asset_inventory_page_returns_zero_pages_for_empty_inventory():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [count_result, item_result]

    response = await list_assets_page(
        q=None, asset_type=None, criticality=None, lifecycle_status=None,
        direction=None, owner=None, classification=None, location=None,
        include_retired=False, page=1, page_size=25, db=db,
        current_user=MagicMock(role="admin"),
    )

    assert response["items"] == []
    assert response["total"] == 0
    assert response["pages"] == 0


def test_canonical_inventory_filters_cover_all_shared_dimensions():
    from sqlalchemy.dialects import postgresql
    from app.api.v1.endpoints.assets import _build_asset_inventory_filters

    filters = _build_asset_inventory_filters(
        q="  serveur  ",
        asset_type="hardware",
        criticality="Critique",
        lifecycle_status="Actif",
        direction=" DI ",
        owner=" Exploitation ",
        classification="Confidentiel",
        location=" Tunis ",
        include_retired=False,
    )
    sql = " AND ".join(
        str(item.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        for item in filters
    )

    assert "assets.retired_at IS NULL" in sql
    assert "assets.lifecycle_status NOT IN ('Retiré', 'Décommissionné')" in sql
    assert "assets.name ILIKE '%serveur%'" in sql
    assert "assets.reference ILIKE '%serveur%'" in sql
    assert "assets.hostname ILIKE '%serveur%'" in sql
    assert "assets.fqdn ILIKE '%serveur%'" in sql
    assert "assets.asset_type = 'hardware'" in sql
    assert "assets.criticality = 'Critique'" in sql
    assert "assets.lifecycle_status = 'Actif'" in sql
    assert "assets.direction ILIKE 'DI'" in sql
    assert "assets.owner ILIKE '%Exploitation%'" in sql
    assert "assets.classification = 'Confidentiel'" in sql
    assert "assets.location ILIKE '%Tunis%'" in sql


def test_canonical_inventory_filters_can_explicitly_include_retired_assets():
    from sqlalchemy.dialects import postgresql
    from app.api.v1.endpoints.assets import _build_asset_inventory_filters

    filters = _build_asset_inventory_filters(include_retired=True)
    sql = " AND ".join(
        str(item.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        for item in filters
    )

    assert filters == []
    assert "retired_at" not in sql
    assert "lifecycle_status NOT IN" not in sql
