"""PostgreSQL tests for transactional admin account lifecycle mutations."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints import admin_users
from app.api.v1.endpoints.admin_users import AdminUserUpdate, update_user
from app.models.audit_outbox import AuditOutbox
from app.models.refresh_token_session import RefreshTokenSession
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "PATCH",
            "path": "/api/v1/admin/users/test",
            "headers": [(b"user-agent", b"pgcc-admin-user-integration-test")],
            "client": ("127.0.0.1", 12345),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


async def _seed(sessions):
    actor_id, target_id = uuid4(), uuid4()
    actor = User(
        id=actor_id,
        email=f"phase0-admin-{actor_id.hex}@example.invalid",
        full_name="Phase 0 admin actor",
        role="admin",
        password_hash="not-used",
        is_active=True,
        mfa_enabled=True,
        auth_version=0,
        must_change_password=False,
    )
    target = User(
        id=target_id,
        email=f"phase0-target-{target_id.hex}@example.invalid",
        full_name="Phase 0 target",
        role="viewer",
        password_hash="not-used",
        is_active=True,
        mfa_enabled=False,
        mfa_secret="stale-encrypted-secret",
        backup_codes_hashed=["stale-hash"],
        auth_version=0,
        must_change_password=False,
    )
    session = RefreshTokenSession(
        user_id=target_id,
        token_jti_hash=(uuid4().hex * 2)[:64],
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    async with sessions() as db:
        # Persist parent user rows before the FK-dependent refresh session.
        db.add_all([actor, target])
        await db.commit()
        db.add(session)
        await db.commit()
        await db.refresh(actor)
        await db.refresh(target)
    return actor_id, target_id, session.id


async def _cleanup(sessions, actor_id, target_id):
    async with sessions() as db:
        await db.execute(
            delete(AuditOutbox).where(
                AuditOutbox.payload["resource_id"].astext == str(target_id)
            )
        )
        await db.execute(delete(User).where(User.id.in_([actor_id, target_id])))
        await db.commit()


@pytest.mark.asyncio
async def test_admin_role_change_revokes_refresh_session_and_audits_atomically():
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id, target_id, session_id = await _seed(sessions)
    try:
        async with sessions() as db:
            actor_in_session = await db.get(User, actor_id)
            result = await update_user(
                user_id=target_id,
                payload=AdminUserUpdate(role="auditor"),
                request=_request(),
                db=db,
                current_user=actor_in_session,
            )
            assert result.role == "auditor"
            assert result.auth_version == 1

        async with sessions() as verify:
            target = await verify.get(User, target_id)
            token_session = await verify.get(RefreshTokenSession, session_id)
            audit_events = (
                await verify.execute(
                    select(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(target_id),
                        AuditOutbox.payload["action"].astext == "ADMIN_USER_UPDATED",
                    )
                )
            ).scalars().all()
            assert target.role == "auditor"
            assert target.auth_version == 1
            assert token_session.revoked_at is not None
            assert len(audit_events) == 1
    finally:
        await _cleanup(sessions, actor_id, target_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_admin_audit_failure_rolls_back_account_change_and_session_revocation(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id, target_id, session_id = await _seed(sessions)

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit outbox failure")

    monkeypatch.setattr(admin_users, "enqueue_audit_event", fail_audit)
    try:
        async with sessions() as db:
            actor_in_session = await db.get(User, actor_id)
            with pytest.raises(RuntimeError, match="simulated audit outbox failure"):
                await update_user(
                    user_id=target_id,
                    payload=AdminUserUpdate(role="auditor"),
                    request=_request(),
                    db=db,
                    current_user=actor_in_session,
                )

        async with sessions() as verify:
            target = await verify.get(User, target_id)
            token_session = await verify.get(RefreshTokenSession, session_id)
            assert target.role == "viewer"
            assert target.auth_version == 0
            assert token_session.revoked_at is None
    finally:
        await _cleanup(sessions, actor_id, target_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_mfa_reset_invalidates_access_and_refresh_sessions_even_when_already_disabled():
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id, target_id, session_id = await _seed(sessions)
    try:
        async with sessions() as db:
            actor = await db.get(User, actor_id)
            result = await admin_users.reset_user_mfa(
                user_id=target_id,
                request=_request(),
                db=db,
                current_user=actor,
            )
            assert result.auth_version == 1
            assert result.mfa_enabled is False

        async with sessions() as verify:
            target = await verify.get(User, target_id)
            token_session = await verify.get(RefreshTokenSession, session_id)
            events = (
                await verify.execute(
                    select(AuditOutbox).where(
                        AuditOutbox.payload["resource_id"].astext == str(target_id),
                        AuditOutbox.payload["action"].astext == "ADMIN_USER_MFA_RESET",
                    )
                )
            ).scalars().all()
            assert target.auth_version == 1
            assert target.mfa_secret is None
            assert target.backup_codes_hashed is None
            assert token_session.revoked_at is not None
            assert len(events) == 1
    finally:
        await _cleanup(sessions, actor_id, target_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_admin_cannot_mutate_accounts_after_concurrent_role_change():
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_id, target_id, session_id = await _seed(sessions)
    try:
        async with sessions() as stale_session:
            stale_actor = await stale_session.get(User, actor_id)
            assert stale_actor.role == "admin"
            assert stale_actor.auth_version == 0

            async with sessions() as concurrent:
                changed_actor = await concurrent.get(User, actor_id)
                changed_actor.role = "auditor"
                await concurrent.commit()

            with pytest.raises(HTTPException) as denied:
                await update_user(
                    user_id=target_id,
                    payload=AdminUserUpdate(role="auditor"),
                    request=_request(),
                    db=stale_session,
                    current_user=stale_actor,
                )
            assert denied.value.status_code == 403

        async with sessions() as verify:
            target = await verify.get(User, target_id)
            assert target.role == "viewer"
            assert target.auth_version == 0
    finally:
        await _cleanup(sessions, actor_id, target_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_admin_demotion_preserves_one_active_mfa_admin():
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    actor_a_id, actor_b_id, session_id = await _seed(sessions)
    try:
        async with sessions() as setup:
            actor_b = await setup.get(User, actor_b_id)
            actor_b.role = "admin"
            actor_b.mfa_enabled = True
            await setup.commit()

        barrier = asyncio.Barrier(2)

        async def demote(actor_id, target_id):
            async with sessions() as db:
                actor = await db.get(User, actor_id)
                await barrier.wait()
                try:
                    result = await update_user(
                        user_id=target_id,
                        payload=AdminUserUpdate(role="auditor"),
                        request=_request(),
                        db=db,
                        current_user=actor,
                    )
                    return ("success", result.id)
                except HTTPException as exc:
                    return (exc.status_code, None)

        outcomes = await asyncio.gather(
            demote(actor_a_id, actor_b_id),
            demote(actor_b_id, actor_a_id),
        )
        assert sum(outcome[0] == "success" for outcome in outcomes) >= 1
        assert sum(outcome[0] == 403 for outcome in outcomes) in {0, 1}

        async with sessions() as verify:
            remaining_admins = (
                await verify.execute(
                    select(User).where(
                        User.role == "admin",
                        User.is_active.is_(True),
                        User.mfa_enabled.is_(True),
                    )
                )
            ).scalars().all()
            assert len(remaining_admins) == 1
            actor_a = await verify.get(User, actor_a_id)
            actor_b = await verify.get(User, actor_b_id)
            assert {actor_a.role, actor_b.role} == {"admin", "auditor"}
    finally:
        await _cleanup(sessions, actor_a_id, actor_b_id)
        await engine.dispose()

