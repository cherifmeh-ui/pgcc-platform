# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ PGCC backend démarré (Phase 0 - squelette)")
    yield
    print("🛑 PGCC backend arrêté")


app = FastAPI(
    title="PGCC API - Plateforme de Gouvernance Cyber CTF",
    version=settings.APP_VERSION,
    description=(
        "Socle de gouvernance cyber interne pour la Compagnie Tunisienne de Forage. "
        "Phase 0 : squelette minimal."
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
        "phase": "0 - squelette",
    }


@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "healthy",
        "service": "pgcc-backend",
        "phase": 0,
        "environment": settings.ENVIRONMENT,
        "ai_enabled": settings.AI_ENABLED,
    }