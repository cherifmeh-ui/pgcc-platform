"""Seed one isolated refresh-session fixture for the Playwright/PostgreSQL CI test.

This script is CI-only. It prints the one-time test refresh token to stdout;
the workflow must mask it and pass it only to the ephemeral browser job.
"""
import asyncio
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_refresh_token, decode_token, hash_password
from app.models.refresh_token_session import RefreshTokenSession
from app.models.user import User

EMAIL = "phase0-browser-refresh@example.invalid"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == EMAIL))
        user = existing.scalar_one_or_none()
        if user is not None:
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()

        user = User(
            email=EMAIL,
            full_name="Ephemeral browser refresh integration",
            role="auditor",
            password_hash=hash_password("Ephemeral-CI-Only-Password!2026"),
            must_change_password=False,
            is_active=True,
            mfa_enabled=False,
            mfa_secret=None,
            mfa_confirmed_at=None,
            backup_codes_hashed=[],
            auth_version=0,
        )
        db.add(user)
        await db.flush()

        refresh_token = create_refresh_token(
            subject=user.email,
            role=user.role,
            mfa_enabled=user.mfa_enabled,
            auth_version=user.auth_version,
            mfa_confirmed_at=None,
        )
        claims = decode_token(refresh_token, expected_type="refresh")
        expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        db.add(RefreshTokenSession(
            user_id=user.id,
            token_jti_hash=hashlib.sha256(claims["jti"].encode("utf-8")).hexdigest(),
            expires_at=expires_at,
        ))
        await db.commit()

    print(json.dumps({"refresh_token": refresh_token}))


if __name__ == "__main__":
    asyncio.run(main())
