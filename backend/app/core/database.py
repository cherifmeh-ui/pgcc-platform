# backend/app/core/database.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings

Base = declarative_base()

# Engine créé uniquement si DATABASE_URL est fourni.
# En Phase 0 (URL vide), engine = None et get_db lève une erreur claire.
engine = (
    create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
    )
    if settings.DATABASE_URL
    else None
)

AsyncSessionLocal = (
    async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    if engine
    else None
)


async def get_db():
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Base de données non configurée (DATABASE_URL vide). "
            "Phase 0 : la DB n'est pas encore branchée."
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise