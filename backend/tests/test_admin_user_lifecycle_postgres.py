"""PostgreSQL tests for transactional admin account lifecycle mutations."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import Request
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
        auth_version=0,
        must_change_password=False,
    )
    session = RefreshTokenSession(
        user_id=target_id,
        token_jti_hash=(uuid4().hex * 2)[:64],
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    async with sessions() as db:
        db.add_all([actor, target, session])
        await db.commit()
        await db.refresh(actor)
        await db.refresh(target)
    return actor_id, target_id, session.id


async def _cleanup(sessions, actor_id, target_id):
    async with sessions() as db:
        await db.execute(\n            delete(AuditOutbox).where(\n                AuditOutbox.payload[\"resource_id\"].astext == str(target_id)\n            )\n        )\n        await db.execute(delete(User).where(User.id.in_([actor_id, target_id])))
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
    actor_id, target_id, actor, session_id = await _seed(sessions)

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
