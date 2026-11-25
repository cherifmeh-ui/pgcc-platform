"""PostgreSQL concurrency tests for multi-session authentication throttling."""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.auth_rate_limit_bucket import AuthRateLimitBucket
from app.services.auth_rate_limiter import enforce_auth_rate_limit, rate_limit_bucket_key

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
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": ("198.51.100.42", 12345),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


@pytest.mark.asyncio
async def test_login_rate_limit_is_atomic_across_concurrent_database_sessions():
    engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ip_key = rate_limit_bucket_key("login:ip", "198.51.100.42")
    account_key = rate_limit_bucket_key("login:account", "parallel@example.test")
    try:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AuthRateLimitBucket).where(
                    AuthRateLimitBucket.bucket_key.in_([ip_key, account_key])
                )
            )
            await cleanup.commit()

        async def attempt() -> int:
            async with sessions() as db:
                try:
                    await enforce_auth_rate_limit(
                        db,
                        _request(),
                        "login",
                        subject="parallel@example.test",
                    )
                    return 200
                except HTTPException as exc:
                    return exc.status_code

        outcomes = await asyncio.gather(*(attempt() for _ in range(25)))
        assert outcomes.count(200) == 20
        assert outcomes.count(429) == 5

        async with sessions() as verify:
            ip_bucket = await verify.get(AuthRateLimitBucket, ip_key)
            account_bucket = await verify.get(AuthRateLimitBucket, account_key)
            assert ip_bucket is not None
            assert account_bucket is not None
            assert ip_bucket.attempts == 21
            assert ip_bucket.blocked_until is not None
            assert account_bucket.attempts == 20
            assert account_bucket.blocked_until is None
            assert ip_bucket.bucket_key != "198.51.100.42"
            assert account_bucket.bucket_key != "parallel@example.test"
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(AuthRateLimitBucket).where(
                    AuthRateLimitBucket.bucket_key.in_([ip_key, account_key])
                )
            )
            await cleanup.commit()
        await engine.dispose()
