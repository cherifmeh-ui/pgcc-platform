from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.api.v1.endpoints.assets import _lifecycle_retirement_marker, _relationship_assets_are_active, _would_create_dependency_cycle


A = UUID("00000000-0000-0000-0000-000000000001")
B = UUID("00000000-0000-0000-0000-000000000002")
C = UUID("00000000-0000-0000-0000-000000000003")


@pytest.mark.asyncio
async def test_dependency_cycle_detected_when_path_exists():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(A, B), (B, C)]
    db.execute.return_value = result

    assert await _would_create_dependency_cycle(db, C, A) is True


@pytest.mark.asyncio
async def test_dependency_cycle_not_detected_for_new_branch():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(A, B), (B, C)]
    db.execute.return_value = result

    assert await _would_create_dependency_cycle(db, A, C) is False


@pytest.mark.asyncio
async def test_dependency_cycle_detection_handles_existing_cycle_safely():
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(A, B), (B, A)]
    db.execute.return_value = result

    assert await _would_create_dependency_cycle(db, C, A) is False


def test_relationship_requires_both_assets_to_be_active():
    assert _relationship_assets_are_active([(A, None), (B, None)]) is True


def test_relationship_rejects_retired_asset_endpoint():
    from datetime import datetime, timezone

    retired_at = datetime.now(timezone.utc)
    assert _relationship_assets_are_active([(A, None), (B, retired_at)]) is False


def test_relationship_rejects_missing_asset_endpoint():
    assert _relationship_assets_are_active([(A, None)]) is False

def test_lifecycle_retired_status_sets_marker():
    marker = _lifecycle_retirement_marker("Retiré", None)
    assert marker is not None


def test_lifecycle_decommissioned_status_sets_marker():
    marker = _lifecycle_retirement_marker("Décommissionné", None)
    assert marker is not None


def test_lifecycle_reactivation_clears_marker():
    existing = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _lifecycle_retirement_marker("Actif", existing) is None


def test_lifecycle_update_without_status_preserves_marker():
    existing = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _lifecycle_retirement_marker(None, existing) == existing


def test_lifecycle_retirement_preserves_existing_timestamp():
    existing = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _lifecycle_retirement_marker("Retiré", existing) == existing
