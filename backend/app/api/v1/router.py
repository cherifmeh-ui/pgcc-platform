# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints.me import router as me_router

api_router = APIRouter()

# On ajoute ici les sous-routers au fur et à mesure des phases.
# Phase 2 : seulement /me pour valider le RBAC.
api_router.include_router(me_router)