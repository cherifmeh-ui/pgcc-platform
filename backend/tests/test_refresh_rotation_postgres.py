"""PostgreSQL-backed concurrency tests for persisted refresh-session rotation.

These tests require a disposable database migrated to Alembic head. They are
skipped locally when PGCC_INTEGRATION_DATABASE_URL is not configured.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.refresh_token_session import RefreshTokenSession
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_concurrent_rotation_has_exactly_one_winner_and_revokes_old_session():
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    old_hash = uuid.uuid4().hex
    new_hash = uuid.uuid4().hex
    email = f"phase0-concurrency-{user_id.hex}@example.invalid"
    now = datetime.now(timezone.utc)

    async with sessions() as setup:
        setup.add(User(
            id=user_id,
            email=email,
            full_name="Phase 0 concurrency test",
            role="viewer",
            password_hash="not-used",
            must_change_password=False,
            is_active=True,
            mfa_enabled=True,
        ))
        setup.add(RefreshTokenSession(
            user_id=user_id,
            token_jti_hash=old_hash,
            expires_at=now + timedelta(days=1),
        ))
        await setup.commit()

    async def rotate(replacement_hash: str) -> bool:
        async with sessions() as db:
            async with db.begin():
                # The endpoint uses the user row as its serialization lock.
                await db.execute(select(User).where(User.id == user_id).with_for_update())
                session = (await db.execute(
                    select(RefreshTokenSession)
                    .where(RefreshTokenSession.token_jti_hash == old_hash)
                    .with_for_update()
                )).scalar_one()
                if session.revoked_at is not None:
                    return False
                session.revoked_at = datetime.now(timezone.utc)
                session.replaced_by_jti_hash = replacement_hash
                db.add(RefreshTokenSession(
                    user_id=user_id,
                    token_jti_hash=replacement_hash,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                ))
                return True

    try:
        results = await asyncio.gather(rotate(new_hash), rotate(uuid.uuid4().hex))
        assert sorted(results) == [False, True]

        async with sessions() as verify:
            old_session = (await verify.execute(
                select(RefreshTokenSession).where(
                    RefreshTokenSession.token_jti_hash == old_hash
                )
            )).scalar_one()
            active_sessions = (await verify.execute(
                select(RefreshTokenSession).where(
                    RefreshTokenSession.user_id == user_id,
                    RefreshTokenSession.revoked_at.is_(None),
                )
            )).scalars().all()
            assert old_session.revoked_at is not None
            assert len(active_sessions) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                # Delete user; FK cascade removes refresh sessions.
                __import__("sqlalchemy").delete(User).where(User.id == user_id)
            )
            await cleanup.commit()
        await engine.dispose()
