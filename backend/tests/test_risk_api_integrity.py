from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.risks import create_risk
from app.schemas.risk import RiskCreate


@pytest.mark.asyncio
async def test_create_risk_rejects_case_normalized_duplicate_reference():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc:
        await create_risk(
            RiskCreate(ref="risk-001", title="Risque de test"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="rssi@example.invalid"),
        )

    assert exc.value.status_code == 409
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_risk_maps_database_uniqueness_race_to_conflict(monkeypatch):
    from app.api.v1.endpoints import risks

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    db.flush.side_effect = IntegrityError("INSERT risks", {}, Exception("duplicate"))

    audit = AsyncMock()
    monkeypatch.setattr(risks, "enqueue_audit_event", audit)

    with pytest.raises(HTTPException) as exc:
        await create_risk(
            RiskCreate(ref="RISK-002", title="Risque de test"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="rssi@example.invalid"),
        )

    assert exc.value.status_code == 409
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    audit.assert_not_awaited()
