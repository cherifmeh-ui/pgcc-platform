from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.api.v1.endpoints.assets import _would_create_dependency_cycle


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
