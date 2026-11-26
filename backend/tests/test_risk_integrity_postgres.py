"""PostgreSQL enforcement of risk score and reference invariants."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.action_item import ActionItem  # register Risk.actions mapper target
from app.models.risk import Risk

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_database_enforces_risk_score_and_reference_invariants():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    token = uuid4().hex[:12]
    reference = f"PH0-RISK-{token}"
    valid_id = uuid4()
    try:
        async with sessions() as db:
            db.add(Risk(
                id=valid_id,
                ref=reference,
                title="Phase 0 valid risk integrity fixture",
                impact=2,
                likelihood=3,
                risk_level=6,
                status="Ouvert",
            ))
            await db.commit()

        invalid_rows = [
            Risk(
                ref=f"PH0-RISK-SCORE-{token}",
                title="Inconsistent risk score",
                impact=2,
                likelihood=3,
                risk_level=5,
                status="Ouvert",
            ),
            Risk(
                ref=f"PH0-RISK-RANGE-{token}",
                title="Out of range impact",
                impact=6,
                likelihood=1,
                risk_level=6,
                status="Ouvert",
            ),
            Risk(
                ref=reference.lower(),
                title="Case-insensitive duplicate reference",
                impact=2,
                likelihood=3,
                risk_level=6,
                status="Ouvert",
            ),
            Risk(
                ref="   ",
                title="Blank risk reference",
                impact=2,
                likelihood=3,
                risk_level=6,
                status="Ouvert",
            ),
        ]
        for invalid in invalid_rows:
            async with sessions() as db:
                db.add(invalid)
                with pytest.raises(IntegrityError):
                    await db.flush()
                await db.rollback()
    finally:
        async with sessions() as db:
            await db.execute(delete(Risk).where(
                (Risk.id == valid_id)
                | (Risk.ref.like(f"PH0-RISK-SCORE-{token}"))
                | (Risk.ref.like(f"PH0-RISK-RANGE-{token}"))
            ))
            await db.commit()
        await engine.dispose()
