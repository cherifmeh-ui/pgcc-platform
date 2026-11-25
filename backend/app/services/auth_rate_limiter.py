"""Atomic, shared authentication throttling backed by PostgreSQL."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import logging
import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import and_, case, delete, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.auth_rate_limit_bucket import AuthRateLimitBucket

logger = logging.getLogger(__name__)

# (requests per window, window seconds, cooldown seconds). The source-IP
# threshold protects password hashing and token verification; the account
# threshold limits distributed attempts without replacing the account lockout.
AUTH_RATE_LIMIT_POLICIES: dict[str, dict[str, tuple[int, int, int]]] = {
    "login": {
        "ip": (20, 900, 900),
        "account": (20, 900, 900),
    },
    "mfa_confirm": {
        "ip": (30, 900, 900),
        "account": (10, 900, 900),
    },
    "mfa_enrollment": {
        "ip": (10, 900, 900),
        "account": (5, 900, 900),
    },
    "password_change": {
        "ip": (5, 900, 900),
        "account": (5, 900, 900),
    },
    "refresh": {
        "ip": (120, 900, 300),
        "account": (30, 900, 300),
    },
}

BUCKET_RETENTION = timedelta(hours=48)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_source_ip(request: Request) -> str:
    """Use forwarded addresses only when the immediate peer is explicitly trusted."""
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer

    trusted_networks = [
        ipaddress.ip_network(value, strict=False)
        for value in settings.auth_trusted_proxy_ips
    ]
    if not any(peer_ip in network for network in trusted_networks):
        return str(peer_ip)

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return str(peer_ip)
    try:
        chain = [ipaddress.ip_address(item.strip()) for item in forwarded.split(",")]
    except ValueError:
        # Malformed proxy metadata is ignored; the trusted peer remains the
        # only address we can safely assert.
        return str(peer_ip)

    # Walk from the network edge inward and select the first untrusted hop.
    for address in reversed([*chain, peer_ip]):
        if not any(address in network for network in trusted_networks):
            return str(address)
    return str(chain[0]) if chain else str(peer_ip)


def rate_limit_bucket_key(scope: str, identity: str) -> str:
    """HMAC identifiers so raw emails and IP addresses are never persisted."""
    secret = settings.auth_rate_limit_hmac_key
    if len(secret) < 32:
        raise RuntimeError("Authentication rate-limit HMAC key is not configured.")
    message = f"{scope}:{identity.strip().lower()}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


async def _increment_bucket(
    db: AsyncSession,
    *,
    key: str,
    scope: str,
    limit: int,
    window_seconds: int,
    cooldown_seconds: int,
    now: datetime,
) -> datetime | None:
    bucket = AuthRateLimitBucket
    blocked_now = and_(bucket.blocked_until.is_not(None), bucket.blocked_until > now)
    window_expired = or_(
        bucket.window_started_at <= now - timedelta(seconds=window_seconds),
        and_(bucket.blocked_until.is_not(None), bucket.blocked_until <= now),
    )
    next_attempts = case(
        (blocked_now, bucket.attempts),
        (window_expired, 1),
        else_=bucket.attempts + 1,
    )
    next_window_started_at = case(
        (window_expired, now),
        else_=bucket.window_started_at,
    )
    next_blocked_until = case(
        (blocked_now, bucket.blocked_until),
        (window_expired, None),
        (next_attempts > limit, now + timedelta(seconds=cooldown_seconds)),
        else_=None,
    )
    statement = (
        insert(bucket)
        .values(
            bucket_key=key,
            scope=scope,
            window_started_at=now,
            attempts=1,
            blocked_until=None,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[bucket.bucket_key],
            set_={
                "attempts": next_attempts,
                "window_started_at": next_window_started_at,
                "blocked_until": next_blocked_until,
                "updated_at": now,
            },
        )
        .returning(bucket.blocked_until)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def enforce_auth_rate_limit(
    db: AsyncSession,
    request: Request,
    action: str,
    *,
    subject: str | None = None,
    include_ip: bool = True,
) -> None:
    """Persist IP/account counters before the protected endpoint does work.

    The caller invokes this before any business mutation. Committing the
    counters here ensures an HTTP 429 or later endpoint rollback cannot erase
    the throttling state. PostgreSQL upserts serialize concurrent replicas.
    """
    policy = AUTH_RATE_LIMIT_POLICIES.get(action)
    if policy is None:
        raise ValueError(f"Unknown authentication rate-limit action: {action}")

    buckets: list[tuple[str, str, tuple[int, int, int]]] = []
    if include_ip:
        client_ip = get_source_ip(request)
        buckets.append(("ip", client_ip, policy["ip"]))
    if subject is not None:
        buckets.append(("account", subject, policy["account"]))
    if not buckets:
        return

    now = utcnow()
    blocked_until_values: list[datetime] = []
    try:
        for kind, identity, (limit, window_seconds, cooldown_seconds) in buckets:
            scope = f"{action}:{kind}"
            key = rate_limit_bucket_key(scope, identity)
            blocked_until = await _increment_bucket(
                db,
                key=key,
                scope=scope,
                limit=limit,
                window_seconds=window_seconds,
                cooldown_seconds=cooldown_seconds,
                now=now,
            )
            if blocked_until is not None and blocked_until > now:
                blocked_until_values.append(blocked_until)
                if kind == "ip":
                    break
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Authentication rate-limit persistence failed (action=%s)", action)
        raise HTTPException(
            status_code=503,
            detail="Contrôle de sécurité temporairement indisponible. Réessayez plus tard.",
        ) from exc

    if blocked_until_values:
        retry_after = max(
            1,
            math.ceil((max(blocked_until_values) - now).total_seconds()),
        )
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives. Réessayez après le délai indiqué.",
            headers={"Retry-After": str(retry_after)},
        )


async def cleanup_expired_auth_rate_limit_buckets() -> int:
    cutoff = utcnow() - BUCKET_RETENTION
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(AuthRateLimitBucket).where(AuthRateLimitBucket.updated_at < cutoff)
        )
        await db.commit()
        return int(result.rowcount or 0)


async def auth_rate_limit_cleanup_worker(poll_interval_seconds: float = 3600.0) -> None:
    """Bound table growth by expiring inactive IP/account buckets."""
    while True:
        try:
            removed = await cleanup_expired_auth_rate_limit_buckets()
            if removed:
                logger.info("Removed %s expired authentication rate-limit buckets", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Authentication rate-limit cleanup cycle failed")
        await asyncio.sleep(poll_interval_seconds)
