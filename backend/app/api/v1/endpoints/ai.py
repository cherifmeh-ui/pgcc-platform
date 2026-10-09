# backend/app/api/v1/endpoints/ai.py
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.user import User
from app.services.ai_service import ai_service
from app.services.security_logger import log_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["Assistant IA"])


class RiskContext(BaseModel):
    """Schéma Pydantic pour valider les données envoyées par le frontend."""
    ref: str = Field(..., min_length=1, max_length=50, description="Référence unique du risque")
    title: str = Field(..., min_length=1, max_length=500, description="Titre du risque")
    description: str = Field("", max_length=2000, description="Description détaillée")
    threat: str = Field("", max_length=1000, description="Menace associée")
    impact: int = Field(3, ge=1, le=5, description="Impact estimé (1-5)")
    likelihood: int = Field(3, ge=1, le=5, description="Probabilité estimée (1-5)")
    site: str = Field("", max_length=100, description="Site géographique concerné")


@router.post("/rewrite-executive")
async def rewrite_for_dg(
    context: RiskContext,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("ai_assistant", "use"),
):
    """
    Reformule un risque technique en langage DG/PDG.
    Réservé aux rôles autorisés (admin, executive, auditor).
    """
    try:
        # Conversion du modèle Pydantic en dict pour le service
        risk_dict = context.model_dump()
        
        # Appel au service IA
        result_content = await ai_service.rewrite_risk_for_executive(risk_dict)
        
        # Journalisation d'audit (Fire-and-forget, ne bloque pas la réponse si ça échoue)
        try:
            await log_action(
                user_email=current_user.email,
                action="AI_REWRITE_EXECUTIVE",
                resource="risks",
                resource_id=context.ref,
                details="Demande de reformulation DG effectuée via Assistant IA",
                event_type="AI_ASSISTANCE",
                request=request,
            )
        except Exception as log_err:
            logger.warning(f"Échec log audit IA: {log_err}")
        
        return {"success": True, "content": result_content}
        
    except HTTPException as he:
        # Propager directement les erreurs HTTP personnalisées (timeout, connect error...)
        raise he
    except Exception as e:
        logger.exception(f"Erreur critique endpoint AI Rewrite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne lors de la génération IA: {str(e)}"
        )


@router.post("/suggest-controls")
async def suggest_iso_measures(
    context: RiskContext,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("ai_assistant", "use"),
):
    """
    Propose des contre-mesures ISO 27002 pour un risque donné.
    Retourne une liste structurée JSON.
    """
    try:
        risk_dict = context.model_dump()
        
        # Appel au service IA
        controls_list = await ai_service.suggest_iso_controls(risk_dict)
        
        # Journalisation d'audit
        try:
            await log_action(
                user_email=current_user.email,
                action="AI_SUGGEST_CONTROLS",
                resource="risks",
                resource_id=context.ref,
                details=f"Suggestion de {len(controls_list)} contrôles ISO générée",
                event_type="AI_ASSISTANCE",
                request=request,
            )
        except Exception as log_err:
            logger.warning(f"Échec log audit IA Controls: {log_err}")
        
        return {"success": True, "controls": controls_list}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Erreur critique endpoint AI Controls: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne lors de la suggestion de contrôles: {str(e)}"
        )