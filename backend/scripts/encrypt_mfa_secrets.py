"""Encrypt legacy plaintext MFA secrets and rotate old Fernet keys.

Run from the backend directory:
    python scripts/encrypt_mfa_secrets.py --dry-run
    python scripts/encrypt_mfa_secrets.py

Set MFA_ENCRYPTION_KEYS to a comma-separated key ring before running. The first
key encrypts all migrated values; later keys are accepted for decryption only.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.user import User
from app.services.mfa_encryption import get_mfa_secret


async def migrate(dry_run: bool) -> tuple[int, int]:
    engine = create_async_engine(settings.DATABASE_URL, pool_size=2, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    scanned = 0
    changed = 0
    try:
        async with sessions() as db:
            result = await db.execute(
                select(User)
                .where(User.mfa_secret.is_not(None))
                .with_for_update()
            )
            users = result.scalars().all()
            for user in users:
                scanned += 1
                previous = user.mfa_secret
                get_mfa_secret(user)
                if user.mfa_secret != previous:
                    changed += 1
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
        return scanned, changed
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt legacy MFA secrets and rotate Fernet keys.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without committing.")
    args = parser.parse_args()
    scanned, changed = asyncio.run(migrate(args.dry_run))
    action = "would update" if args.dry_run else "updated"
    print(f"Scanned {scanned} MFA secret(s); {action} {changed}. No secret values were logged.")


if __name__ == "__main__":
    main()
