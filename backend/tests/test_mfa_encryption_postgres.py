"""PostgreSQL persistence tests for encrypted MFA shared secrets."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.user import User
from app.services.mfa_encryption import (
    MFA_SECRET_PREFIX,
    assert_no_plaintext_mfa_secrets,
    get_mfa_secret,
)

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_postgres_mfa_secret_is_encrypted_persisted_and_startup_verifiable():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    email = f"phase0-mfa-encryption-{user_id.hex}@example.invalid"
    legacy_secret = "JBSWY3DPEHPK3PXP"
    try:
        async with sessions() as setup:
            setup.add(User(
                id=user_id, email=email, full_name="MFA Encryption Integration",
                role="viewer", password_hash="not-used", mfa_secret=legacy_secret,
                mfa_enabled=True, must_change_password=False, is_active=True,
            ))
            await setup.commit()

        async with sessions() as db:
            user = (await db.execute(
                select(User).where(User.id == user_id).with_for_update()
            )).scalar_one()
            assert get_mfa_secret(user) == legacy_secret
            assert user.mfa_secret.startswith(MFA_SECRET_PREFIX)
            assert legacy_secret not in user.mfa_secret
            await db.commit()

        async with sessions() as verify:
            stored = (await verify.execute(
                select(User).where(User.id == user_id)
            )).scalar_one()
            assert stored.mfa_secret.startswith(MFA_SECRET_PREFIX)
            assert get_mfa_secret(stored) == legacy_secret
            await assert_no_plaintext_mfa_secrets(verify)
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()
