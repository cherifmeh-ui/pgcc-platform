# backend/app/main.py
import asyncio
from contextlib import asynccontextmanager, suppress

from sqlalchemy import text

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.api.v1.router import api_router
from app.api.v1.endpoints.auth import router as auth_router
from app.services.security_logger import audit_outbox_worker
from app.services.auth_rate_limiter import auth_rate_limit_cleanup_worker
from app.services.mfa_encryption import assert_no_plaintext_mfa_secrets


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models import user, security_log, audit_outbox, risk, asset, supplier, refresh_token_session, auth_rate_limit_bucket, action_verification, iso_control_evidence  # noqa: F401

    if settings.ENVIRONMENT.lower() == "development":
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        print("PGCC | development schema ensured via create_all")
    else:
        print("PGCC | production schema must be managed through Alembic migrations")
        async with AsyncSessionLocal() as db:
            await assert_no_plaintext_mfa_secrets(db)
            # Fail startup if the distributed auth limiter migration is missing.
            await db.execute(text("SELECT bucket_key FROM auth_rate_limit_buckets LIMIT 0"))
    audit_worker = asyncio.create_task(audit_outbox_worker())
    rate_limit_cleanup_worker = asyncio.create_task(auth_rate_limit_cleanup_worker())
    try:
        yield
    finally:
        audit_worker.cancel()
        rate_limit_cleanup_worker.cancel()
        with suppress(asyncio.CancelledError):
            await audit_worker
        with suppress(asyncio.CancelledError):
            await rate_limit_cleanup_worker
    print("🛑 PGCC | arrêt")


app = FastAPI(
    title="PGCC API - Plateforme de Gouvernance Cyber CTF",
    version=settings.APP_VERSION,
    description=(
        "Socle de gouvernance cyber interne pour la Compagnie Tunisienne de Forage. "
        "Phase 4 : Audit immuable + Module Risques CRUD."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Toutes les routes API sont préfixées par /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "🛡️ PGCC API - Plateforme de Gouvernance Cyber CTF",
        "status": "OK",
        "version": settings.APP_VERSION,
        "phase": "2 - RBAC backend",
    }


@app.get("/health", include_in_schema=False)
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "pgcc-backend",
        "phase": 4,
        "environment": settings.ENVIRONMENT,
        "ai_enabled": settings.AI_ENABLED,
        "db": db_status,
    }