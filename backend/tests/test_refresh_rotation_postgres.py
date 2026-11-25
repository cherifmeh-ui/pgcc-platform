"""PostgreSQL-backed concurrency tests for persisted refresh-session rotation.

These tests require a disposable database migrated to Alembic head. They are
skipped locally when PGCC_INTEGRATION_DATABASE_URL is not configured.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
import hashlib

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.refresh_token_session import RefreshTokenSession
from app.models.audit_outbox import AuditOutbox
from app.api.v1.endpoints import auth as auth_endpoint
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
        # Commit the referenced user first: these ORM models intentionally do
        # not define a relationship, so unit-of-work ordering is not guaranteed.
        await setup.commit()
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

@pytest.mark.asyncio
async def test_refresh_endpoint_rotation_and_replay_are_audited_atomically(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    old_jti = uuid.uuid4().hex
    old_hash = hashlib.sha256(old_jti.encode()).hexdigest()
    email = f"phase0-http-refresh-{user_id.hex}@example.invalid"
    now = datetime.now(timezone.utc)
    issued_tokens = {
        "old-refresh": {
            "sub": email, "jti": old_jti, "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=1)).timestamp()), "type": "refresh",
            "role": "viewer", "mfa_enabled": False, "mfa_confirmed_at": None,
        }
    }
    replacement_counter = 0

    def decode(token, expected_type="access"):
        payload = issued_tokens[token]
        assert payload["type"] == expected_type
        return payload

    def create_refresh(subject, role=None, mfa_enabled=None, mfa_confirmed_at=None):
        nonlocal replacement_counter
        replacement_counter += 1
        token = f"new-refresh-{replacement_counter}"
        issued_tokens[token] = {
            "sub": subject, "jti": uuid.uuid4().hex,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
            "type": "refresh", "role": role,
            "mfa_enabled": mfa_enabled, "mfa_confirmed_at": mfa_confirmed_at,
        }
        return token

    monkeypatch.setattr(auth_endpoint, "decode_token", decode)
    monkeypatch.setattr(auth_endpoint, "create_access_token", lambda **kwargs: "new-access")
    monkeypatch.setattr(auth_endpoint, "create_refresh_token", create_refresh)

    async with sessions() as setup:
        setup.add(User(
            id=user_id, email=email, full_name="HTTP refresh integration",
            role="viewer", password_hash="not-used", must_change_password=False,
            is_active=True, mfa_enabled=False,
        ))
        await setup.commit()
        setup.add(RefreshTokenSession(
            user_id=user_id, token_jti_hash=old_hash,
            expires_at=now + timedelta(days=1),
        ))
        await setup.commit()

    request = Request({
        "type": "http", "method": "POST", "path": "/auth/refresh",
        "headers": [
            (b"cookie", b"pgcc_refresh=old-refresh"),
            (b"origin", b"http://localhost:5173"),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80), "scheme": "http", "query_string": b"",
    })

    async def rotate():
        async with sessions() as db:
            response = Response()
            result = await auth_endpoint.refresh_tokens(
                request=request, response=response, db=db,
                refresh_cookie="old-refresh",
            )
            return result, response

    try:
        results = await asyncio.gather(rotate(), rotate(), return_exceptions=True)
        assert sum(not isinstance(item, BaseException) for item in results) == 1
        successes = [item for item in results if not isinstance(item, BaseException)]
        assert len(successes) == 1
        assert "HttpOnly" in successes[0][1].headers.get("set-cookie", "")
        assert "SameSite=strict" in successes[0][1].headers.get("set-cookie", "")
        assert not hasattr(successes[0][0], "refresh_token")
        failures = [item for item in results if isinstance(item, BaseException)]
        assert len(failures) == 1
        assert isinstance(failures[0], HTTPException)
        assert failures[0].status_code == 401

        async with sessions() as verify:
            old_session = (await verify.execute(
                select(RefreshTokenSession).where(
                    RefreshTokenSession.token_jti_hash == old_hash
                )
            )).scalar_one()
            all_sessions = (await verify.execute(
                select(RefreshTokenSession).where(RefreshTokenSession.user_id == user_id)
            )).scalars().all()
            events = (await verify.execute(
                select(AuditOutbox).where(AuditOutbox.payload["user_email"].astext == email)
            )).scalars().all()
            assert old_session.revoked_at is not None
            assert all(session.revoked_at is not None for session in all_sessions)
            assert {event.payload["action"] for event in events} == {
                "REFRESH_TOKEN_ROTATED", "REFRESH_TOKEN_REUSE_DETECTED"
            }
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                __import__("sqlalchemy").delete(AuditOutbox).where(
                    AuditOutbox.payload["user_email"].astext == email
                )
            )
            await cleanup.execute(
                __import__("sqlalchemy").delete(User).where(User.id == user_id)
            )
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_rolls_back_rotation_if_audit_enqueue_fails(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    old_jti = uuid.uuid4().hex
    old_hash = hashlib.sha256(old_jti.encode()).hexdigest()
    email = f"phase0-refresh-audit-failure-{user_id.hex}@example.invalid"
    now = datetime.now(timezone.utc)
    issued_tokens = {
        "old-refresh": {
            "sub": email, "jti": old_jti, "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=1)).timestamp()), "type": "refresh",
            "role": "viewer", "mfa_enabled": False, "mfa_confirmed_at": None,
        },
        "new-refresh": {
            "sub": email, "jti": uuid.uuid4().hex,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=1)).timestamp()), "type": "refresh",
            "role": "viewer", "mfa_enabled": False, "mfa_confirmed_at": None,
        },
    }
    monkeypatch.setattr(auth_endpoint, "decode_token", lambda token, expected_type="access": issued_tokens[token])
    monkeypatch.setattr(auth_endpoint, "create_access_token", lambda **kwargs: "new-access")
    monkeypatch.setattr(auth_endpoint, "create_refresh_token", lambda subject, **kwargs: "new-refresh")
    monkeypatch.setattr(
        auth_endpoint, "enqueue_audit_event",
        AsyncMock(side_effect=RuntimeError("simulated refresh audit failure")),
    )

    async with sessions() as setup:
        setup.add(User(
            id=user_id, email=email, full_name="Refresh audit rollback",
            role="viewer", password_hash="not-used", must_change_password=False,
            is_active=True, mfa_enabled=False,
        ))
        await setup.commit()
        setup.add(RefreshTokenSession(
            user_id=user_id, token_jti_hash=old_hash,
            expires_at=now + timedelta(days=1),
        ))
        await setup.commit()

    request = Request({
        "type": "http", "method": "POST", "path": "/auth/refresh",
        "headers": [(b"origin", b"http://localhost:5173")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80), "scheme": "http", "query_string": b"",
    })
    try:
        async with sessions() as db:
            with pytest.raises(RuntimeError, match="simulated refresh audit failure"):
                await auth_endpoint.refresh_tokens(
                    request=request, response=Response(), db=db,
                    refresh_cookie="old-refresh",
                )

        async with sessions() as verify:
            stored = (await verify.execute(
                select(RefreshTokenSession).where(RefreshTokenSession.user_id == user_id)
            )).scalars().all()
            assert len(stored) == 1
            assert stored[0].token_jti_hash == old_hash
            assert stored[0].revoked_at is None
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                __import__("sqlalchemy").delete(User).where(User.id == user_id)
            )
            await cleanup.commit()
        await engine.dispose()
