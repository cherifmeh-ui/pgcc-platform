"""PostgreSQL prevents deleting a risk that owns corrective actions."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.action_item import ActionItem
from app.models.risk import Risk

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_database_restricts_risk_deletion_while_actions_exist():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid4().hex[:12]
    risk = Risk(
        ref=f"PH0-ACTION-{token}",
        title="Phase 0 action retention fixture",
        impact=2,
        likelihood=3,
        risk_level=6,
        status="Ouvert",
    )
    risk_id = None
    try:
        async with sessions() as db:
            db.add(risk)
            await db.commit()
            await db.refresh(risk)
            risk_id = risk.id
            action = ActionItem(
                risk_id=risk_id,
                title="Action must survive risk deletion attempt",
            )
            db.add(action)
            await db.commit()
            action_id = action.id

        async with sessions() as db:
            persisted_risk = await db.get(Risk, risk_id)
            await db.delete(persisted_risk)
            with pytest.raises(IntegrityError):
                await db.flush()
            await db.rollback()

        async with sessions() as db:
            assert await db.scalar(select(func.count(Risk.id)).where(Risk.id == risk_id)) == 1
            assert await db.scalar(select(func.count(ActionItem.id)).where(ActionItem.id == action_id)) == 1
    finally:
        if risk_id is not None:
            async with sessions() as db:
                await db.execute(delete(ActionItem).where(ActionItem.risk_id == risk_id))
                await db.execute(delete(Risk).where(Risk.id == risk_id))
                await db.commit()
        await engine.dispose()
