# backend/app/api/v1/router.py
from fastapi import APIRouter

# Imports des routers existants
from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.security_logs import router as security_logs_router
from app.api.v1.endpoints.risks import router as risks_router
from app.api.v1.endpoints.ai import router as ai_router

# ⚠️ CORRECTION CRITIQUE : Le fichier s'appelle "apps.py", pas "applications.py"
from app.api.v1.endpoints.apps import router as apps_router

api_router = APIRouter()

# Inclusion des routes dans le routeur principal
api_router.include_router(me_router)
api_router.include_router(auth_router)
api_router.include_router(security_logs_router)
api_router.include_router(risks_router)
api_router.include_router(ai_router)
api_router.include_router(apps_router)          # ← Utilise apps_router ici