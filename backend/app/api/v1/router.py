# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.security_logs import router as security_logs_router
from app.api.v1.endpoints.risks import router as risks_router
from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.apps import router as apps_router      # ✅ Apps Critiques
from app.api.v1.endpoints.reports import router as reports_router # ✅ Rapports DG
from app.api.v1.endpoints.actions import router as actions_router # ✅ Plans d'Action
from app.api.v1.endpoints.compliance import router as compliance_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.assets import router as assets_router
from app.api.v1.endpoints.suppliers import router as suppliers_router
from app.api.v1.endpoints.admin_users import router as admin_users_router

api_router = APIRouter()

api_router.include_router(me_router)
api_router.include_router(auth_router)
api_router.include_router(security_logs_router)
api_router.include_router(risks_router)
api_router.include_router(ai_router)
api_router.include_router(apps_router)
api_router.include_router(reports_router)
api_router.include_router(actions_router)
api_router.include_router(compliance_router)
api_router.include_router(documents_router)
api_router.include_router(assets_router)
api_router.include_router(suppliers_router)
api_router.include_router(admin_users_router)