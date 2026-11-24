"""PostgreSQL integration tests for append-only security audit logs."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.security_log import SecurityLog

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_security_log_rejects_update_and_delete(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    log_id = uuid4()

    try:
        async with sessions() as db:
            await db.begin()
            db.add(SecurityLog(
                id=log_id,
                event_type="PHASE0_APPEND_ONLY_TEST",
                user_email="phase0@example.invalid",
                action="TEST_INSERT",
                resource="security_logs",
                resource_id=str(log_id),
                details="original immutable evidence",
            ))
            await db.flush()

            with pytest.raises(DBAPIError, match="append-only"):
                async with db.begin_nested():
                    await db.execute(
                        update(SecurityLog)
                        .where(SecurityLog.id == log_id)
                        .values(details="tampered")
                    )

            with pytest.raises(DBAPIError, match="append-only"):
                async with db.begin_nested():
                    await db.execute(
                        delete(SecurityLog).where(SecurityLog.id == log_id)
                    )

            persisted = (await db.execute(
                select(SecurityLog).where(SecurityLog.id == log_id)
            )).scalar_one()
            assert persisted.details == "original immutable evidence"
            # Roll back the outer transaction so the test leaves no audit row.
            await db.rollback()
    finally:
        await engine.dispose()
