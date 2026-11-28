# backend/app/api/v1/endpoints/reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from typing import List, Dict, Any
import datetime
import logging

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.risk import Risk
from app.models.application import Application
from app.models.action_item import ActionItem, ActionStatus # ⬅️ NOUVEL IMPORT
from app.models.user import User

# ⚠️ IMPORT DU SERVICE IA (Adapte si nécessaire selon ta structure)
try:
    from app.services.ai_service import ai_service
except ImportError:
    ai_service = None # Fallback si le module n'est pas trouvé

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Rapports"])


class DgSummaryResponse(BaseModel):
    generated_at: str
    total_risks: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    apps_critical: int
    top_5_risks: List[Dict[str, Any]]
    obsolete_apps: List[str]
    ai_summary: str
    
    # ⬇️ NOUVEAUX CHAMPS POUR LE SUIVI PAC ⬇️
    pac_stats: Dict[str, int] 
    pac_completion_rate: float
    charts_data: Dict[str, Any]


@router.get("/dg-summary", response_model=DgSummaryResponse)
async def generate_dg_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("reports", "generate"),
):
    """
    Génère une synthèse complète pour la Direction Générale.
    Inclut maintenant les métriques du Plan d'Action Correctif (PAC).
    """
    
    try:
        # ==========================================
        # 1. AGGREGATION STATISTIQUES RISQUES
        # ==========================================
        risks_query = await db.execute(select(Risk))
        risks = risks_query.scalars().all()
        
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        categories = {} 
        
        for r in risks:
            lvl = getattr(r, 'risk_level', 0) or 0 
            if lvl >= 20: counts["critical"] += 1
            elif lvl >= 15: counts["high"] += 1
            elif lvl >= 5: counts["medium"] += 1
            else: counts["low"] += 1
            
            # Catégorisation robuste basée sur mots-clés
            cat = "Autre"
            title_lower = (getattr(r, 'title', '') or '').lower()
            threat_lower = (getattr(r, 'threat', '') or '').lower()
            
            if any(k in title_lower or k in threat_lower for k in ["cyberattaque", "phishing", "ransomware", "intrusion", "ddos"]):
                cat = "Malveillance Externe"
            elif any(k in title_lower or k in threat_lower for k in ["panne", "obsolescence", "corruption", "vsat", "raid"]):
                cat = "Technique / Obsolescence"
            elif any(k in title_lower or k in threat_lower for k in ["erreur", "humaine", "partage", "shadow it", "perte"]):
                cat = "Erreur Humaine"
            elif any(k in title_lower or k in threat_lower for k in ["non-conformité", "ancs", "pssi", "audit"]):
                cat = "Conformité Réglementaire"
                
            categories[cat] = categories.get(cat, 0) + 1

        # 2. TOP 5 RISQUES CRITIQUES
        sorted_risks = sorted(risks, key=lambda x: getattr(x, 'risk_level', 0) or 0, reverse=True)[:5]
        top_5_list = [
            {
                "ref": getattr(r, 'ref', 'N/A'), 
                "title": getattr(r, 'title', 'Sans titre'), 
                "score": getattr(r, 'risk_level', 0) or 0, 
                "site": getattr(r, 'site', 'N/A'),
                "status": getattr(r, 'status', 'Inconnu')
            } for r in sorted_risks
        ]

        # 3. APPS OBSOLESCENTES / CRITIQUES
        apps_query = await db.execute(select(Application).where(Application.criticality.in_(["Critique", "Élevée"])))
        apps = apps_query.scalars().all()
        obsolete_names = list(set([getattr(a, 'name', 'Unknown') for a in apps])) 

        # ==========================================
        # 4. NOUVEAU : CALCUL DES STATS PLAN D'ACTION (PAC)
        # ==========================================
        actions_query = await db.execute(select(ActionItem))
        all_actions = actions_query.scalars().all()
        
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        pac_stats = {
            "total": len(all_actions),
            "todo": sum(1 for a in all_actions if a.status == ActionStatus.TODO),
            "in_progress": sum(1 for a in all_actions if a.status == ActionStatus.IN_PROGRESS),
            "done": sum(1 for a in all_actions if a.status == ActionStatus.DONE),
            "blocked": sum(1 for a in all_actions if a.status == ActionStatus.BLOCKED),
            "overdue": sum(1 for a in all_actions 
                          if a.due_date and a.due_date < now_utc 
                          and a.status != ActionStatus.DONE)
        }
        
        # Calcul du taux de complétion (%)
        completion_rate = round((pac_stats["done"] / pac_stats["total"] * 100), 1) if pac_stats["total"] > 0 else 0.0

        # ==========================================
        # 5. APPEL IA POUR SYNTHÈSE EXECUTIVE ENRICHIE
        # ==========================================
        prompt_context = f"""
        Tu es le RSSI de la CTF. Rédige une note de synthèse concise (max 150 mots) pour le PDG.
        
        Contexte Sécurité SI :
        - Total risques ouverts : {len(risks)}
        - Risques Inacceptables/Critiques : {counts['critical']}
        - Applications critiques exposées : {', '.join(obsolete_names[:3]) if obsolete_names else 'Aucune'}...
        
        Contexte Suivi Actions Correctives (PAC) :
        - Tâches totales planifiées : {pac_stats['total']}
        - Tâches terminées : {pac_stats['done']} ({completion_rate}% réussite)
        - Tâches en retard critique : {pac_stats['overdue']}
        
        Ton : Professionnel, alertant mais constructif. Termine par une recommandation prioritaire unique concernant soit la réduction des risques critiques, soit l'accélération des plans d'action en retard.
        """
        
        summary_text = ""
        try:
            if ai_service and hasattr(ai_service, 'generate_text'):
                 try:
                     summary_text = await ai_service.generate_text(prompt_context, model="phi3:latest")
                 except TypeError:
                     summary_text = await ai_service.generate_text(prompt_context)
            else:
                 summary_text = "[INFO] Service IA non disponible. Utiliser les statistiques brutes."
                 
        except Exception as e_ai:
            print(f"⚠️ Erreur appel IA rapport DG: {e_ai}")
            summary_text = f"[ERREUR TEMPORAIRE IA] Impossible de générer la synthèse ({str(e_ai)[:50]}...). Les données chiffrées restent valides."

        return DgSummaryResponse(
            generated_at=datetime.datetime.now().isoformat(),
            total_risks=len(risks),
            critical_count=counts["critical"],
            high_count=counts["high"],
            medium_count=counts["medium"],
            low_count=counts["low"],
            apps_critical=len(apps),
            top_5_risks=top_5_list,
            obsolete_apps=obsolete_names,
            ai_summary=summary_text,
            pac_stats=pac_stats,           # ⬅️ NOUVEAU
            pac_completion_rate=completion_rate, # ⬅️ NOUVEAU
            charts_data={
                "categories": categories,
                "levels": counts,
                "pac_status": {             # ⬅️ DONNÉES BRUTES POUR GRAPHIQUE DONUT
                    "À faire": pac_stats["todo"],
                    "En cours": pac_stats["in_progress"],
                    "Terminé": pac_stats["done"],
                    "Bloqué": pac_stats["blocked"]
                }
            }
        )

    except Exception:
        # Keep diagnostic details server-side; never expose database, stack,
        # provider, or configuration errors through the API response.
        logger.exception("DG report generation failed")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la génération du rapport.",
        )