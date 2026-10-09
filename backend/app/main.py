# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Importer les modeles AVANT create_all pour qu'ils s'enregistrent dans le metadata
    from app.models import user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ PGCC | tables créées/vérifiées (Phase 1)")
    yield
    print("🛑 PGCC | arrêt")


app = FastAPI(
    title="PGCC API - Plateforme de Gouvernance Cyber CTF",
    version=settings.APP_VERSION,
    description=(
        "Socle de gouvernance cyber interne pour la Compagnie Tunisienne de Forage. "
        "Phase 1 : authentification + modèle User + sécurité."
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


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "🛡️ PGCC API - Plateforme de Gouvernance Cyber CTF",
        "status": "OK",
        "version": settings.APP_VERSION,
        "phase": "1 - socle auth + user",
    }


@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "healthy",
        "service": "pgcc-backend",
        "phase": 1,
        "environment": settings.ENVIRONMENT,
        "ai_enabled": settings.AI_ENABLED,
        "db": "branchée",
    }