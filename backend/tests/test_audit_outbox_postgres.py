"""PostgreSQL integration tests for durable audit outbox delivery and retry."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.audit_outbox import AuditOutbox
from app.models.security_log import SecurityLog
from app.services import security_logger

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_audit_event_is_durable_and_retried_after_delivery_failure(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=2, max_overflow=0)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            sessions = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            monkeypatch.setattr(security_logger, "AsyncSessionLocal", sessions)
            original_insert = security_logger._insert_security_log

            def fail_once(_session, _event):
                raise RuntimeError("simulated transient sink failure")

            monkeypatch.setattr(security_logger, "_insert_security_log", fail_once)
            event_id = await security_logger.log_action(
                user_email="phase0@example.invalid",
                action="OUTBOX_RETRY_TEST",
                resource="audit_outbox",
                details="durable event retry test",
                event_type="PHASE0_OUTBOX",
            )

            async with sessions() as verify:
                queued = await verify.get(AuditOutbox, event_id)
                assert queued is not None
                assert queued.delivered_at is None
                assert queued.attempts == 1
                assert queued.last_error == "RuntimeError"
                logs = (await verify.execute(
                    select(SecurityLog).where(SecurityLog.event_id == event_id)
                )).scalars().all()
                assert logs == []

            monkeypatch.setattr(security_logger, "_insert_security_log", original_insert)
            assert await security_logger.deliver_pending_audit_events(
                limit=10, event_id=event_id
            ) == 1
            # Re-running delivery for an already delivered event is idempotent.
            assert await security_logger.deliver_pending_audit_events(
                limit=10, event_id=event_id
            ) == 0

            async with sessions() as verify:
                queued = await verify.get(AuditOutbox, event_id)
                assert queued.delivered_at is not None
                assert queued.last_error is None
                log = (await verify.execute(
                    select(SecurityLog).where(SecurityLog.event_id == event_id)
                )).scalar_one()
                assert log.action == "OUTBOX_RETRY_TEST"
                assert log.details == "durable event retry test"

            await outer.rollback()
    finally:
        await engine.dispose()



@pytest.mark.asyncio
async def test_business_transaction_and_audit_outbox_share_commit_boundary():
    """A rolled-back business transaction must not leave a committed audit row."""
    from app.services.security_logger import enqueue_audit_event

    engine = create_async_engine(DATABASE_URL, pool_size=2, max_overflow=0)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            sessions = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with sessions() as session:
                event_id = await enqueue_audit_event(
                    session,
                    user_email="phase0@example.invalid",
                    action="RISK_CREATE_ROLLBACK_TEST",
                    resource="risks",
                    resource_id="RISK-TX-ROLLBACK",
                    details="must share the business transaction",
                )
                assert await session.get(AuditOutbox, event_id) is not None
                await session.rollback()

            async with sessions() as verify:
                assert await verify.get(AuditOutbox, event_id) is None

            async with sessions() as session:
                committed_id = await enqueue_audit_event(
                    session,
                    user_email="phase0@example.invalid",
                    action="RISK_CREATE_COMMIT_TEST",
                    resource="risks",
                    resource_id="RISK-TX-COMMIT",
                    details="same transaction committed",
                )
                await session.commit()

            async with sessions() as verify:
                committed = await verify.get(AuditOutbox, committed_id)
                assert committed is not None
                assert committed.delivered_at is None

            await outer.rollback()
    finally:
        await engine.dispose()
