"""PostgreSQL concurrency coverage for one-time MFA recovery codes."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints import auth as auth_endpoint
from app.core.security import create_pre_auth_token, hash_backup_codes
from app.models.audit_outbox import AuditOutbox
from app.models.refresh_token_session import RefreshTokenSession
from app.models.user import User
from app.services.mfa_encryption import encrypt_mfa_secret

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/confirm-mfa",
            "headers": [(b"user-agent", b"pgcc-mfa-recovery-concurrency-test")],
            "client": ("127.0.0.1", 12345),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


@pytest.mark.asyncio
async def test_one_mfa_recovery_code_cannot_be_consumed_by_two_concurrent_sessions(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    email = f"phase0-mfa-recovery-{user_id.hex}@example.invalid"
    recovery_code = "ABCDE-12345"
    token = create_pre_auth_token(email, "viewer", auth_version=0)

    monkeypatch.setattr(auth_endpoint, "enforce_auth_rate_limit", AsyncMock())
    monkeypatch.setattr(auth_endpoint, "verify_mfa", lambda secret, code: False)

    try:
        async with sessions() as setup:
            setup.add(
                User(
                    id=user_id,
                    email=email,
                    full_name="Phase 0 MFA recovery concurrency",
                    role="viewer",
                    password_hash="not-used",
                    is_active=True,
                    must_change_password=False,
                    mfa_enabled=True,
                    mfa_secret=encrypt_mfa_secret("JBSWY3DPEHPK3PXP"),
                    mfa_confirmed_at=datetime.now(timezone.utc),
                    backup_codes_hashed=hash_backup_codes([recovery_code]),
                    auth_version=0,
                )
            )
            await setup.commit()

        async def consume() -> str:
            async with sessions() as db:
                try:
                    await auth_endpoint.confirm_mfa(
                        payload=auth_endpoint.ConfirmMfaRequest(
                            pre_auth_token=token,
                            mfa_code=recovery_code,
                        ),
                        request=_request(),
                        response=Response(),
                        db=db,
                    )
                    return "success"
                except HTTPException as exc:
                    return f"denied:{exc.status_code}"

        outcomes = await asyncio.gather(consume(), consume())
        assert outcomes.count("success") == 1
        assert outcomes.count("denied:401") == 1

        async with sessions() as verify:
            user = await verify.get(User, user_id)
            active_sessions = await verify.scalar(
                select(func.count()).select_from(RefreshTokenSession).where(
                    RefreshTokenSession.user_id == user_id,
                    RefreshTokenSession.revoked_at.is_(None),
                )
            )
            audit_count = await verify.scalar(
                select(func.count()).select_from(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext == str(user_id),
                )
            )
            assert user.backup_codes_hashed == []
            assert active_sessions == 1
            assert audit_count == 2
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AuditOutbox).where(
                    AuditOutbox.payload["resource_id"].astext == str(user_id)
                )
            )
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()
