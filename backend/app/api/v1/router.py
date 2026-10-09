# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.security_logs import router as security_logs_router  # ← AJOUTÉ
from app.api.v1.endpoints.risks import router as risks_router                  # ← AJOUTÉ

api_router = APIRouter()

api_router.include_router(me_router)
api_router.include_router(auth_router)
api_router.include_router(security_logs_router)  # ← AJOUTÉ
api_router.include_router(risks_router)          # ← AJOUTÉ