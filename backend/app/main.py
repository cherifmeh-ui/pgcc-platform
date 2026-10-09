# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.router import api_router
from app.api.v1.endpoints.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models import user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ PGCC | tables créées/vérifiées (Phase 2)")
    yield
    print("🛑 PGCC | arrêt")


app = FastAPI(
    title="PGCC API - Plateforme de Gouvernance Cyber CTF",
    version=settings.APP_VERSION,
    description=(
        "Socle de gouvernance cyber interne pour la Compagnie Tunisienne de Forage. "
        "Phase 2 : RBAC backend + dépendances d'authentification."
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
    return {
        "status": "healthy",
        "service": "pgcc-backend",
        "phase": 2,
        "environment": settings.ENVIRONMENT,
        "ai_enabled": settings.AI_ENABLED,
        "db": "branchée",
    }