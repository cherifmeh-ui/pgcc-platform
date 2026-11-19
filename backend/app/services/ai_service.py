# backend/app/services/ai_service.py
import json
import logging
from typing import Optional, List, Dict, Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration Réseau & Modèle
OLLAMA_BASE_URL = "http://host.docker.internal:11434"
DEFAULT_MODEL = "phi3:latest" 
# ⚠️ IMPORTANT : Timeout élevé (120s) car le chargement initial du modèle peut être long sur CPU/GPU partagé
TIMEOUT_SECONDS = 180 


class AIService:
    """
    Service souverain d'assistance IA basé sur Ollama local.
    Aucune donnée ne quitte l'infrastructure CTF.
    """

    def __init__(self):
        self.enabled = getattr(settings, 'AI_ENABLED', False)
        self.model = DEFAULT_MODEL
        self.base_url = OLLAMA_BASE_URL

    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Envoie un prompt à Ollama et retourne la réponse texte brute.
        Gère proprement les timeouts, connexions refusées et erreurs serveur.
        """
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="L'assistant IA est désactivé (AI_ENABLED=false)."
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 512, # Limite la longueur pour éviter les réponses interminables
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt

        try:
            logger.info(f" Appel IA vers {self.base_url} avec modèle {self.model}...")
            
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                
                # Vérifie si le statut HTTP est OK (200-299)
                response.raise_for_status()
                
                data = response.json()
                content = data.get("response", "").strip()
                
                if not content:
                    logger.warning("Réponse IA vide reçue.")
                    return ""
                    
                logger.info("✅ Réponse IA générée avec succès.")
                return content
                
        except httpx.TimeoutException:
            logger.error(f"⏱️ TIMEOUT après {TIMEOUT_SECONDS}s lors de l'appel IA.")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="L'IA met trop de temps à répondre. Le modèle est peut-être en train de se charger. Patientez ou essayez un modèle plus léger (phi3)."
            )
        except httpx.ConnectError:
            logger.error("🔌 IMPOSSIBLE DE CONNECTER À OLLAMA via host.docker.internal")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Connexion échouée. Vérifiez que 'ollama serve' tourne ET que le firewall autorise localhost:11434 depuis Docker."
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"💥 Erreur HTTP Ollama: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erreur côté serveur IA: {e.response.status_code}"
            )
        except Exception as e:
            logger.exception(f"💥 ERREUR INATTENDUE SERVICE IA: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Détail technique : {str(e)}"
            )

    # -------------------------------------------------------
    # PROMPTS MÉTIER SPÉCIFIQUES CTF / INDUSTRIEL
    # -------------------------------------------------------

    async def rewrite_risk_for_executive(self, risk_data: dict) -> str:
        """
        Reformule une fiche technique en langage DG/PDG.
        Focus sur l'impact business, financier et opérationnel.
        """
        system_prompt = (
            "Tu es un expert en communication corporate pour une grande entreprise industrielle tunisienne (CTF). "
            "Ton rôle est de traduire des risques cyber techniques en impacts business compréhensibles par la Direction Générale. "
            "Sois concis, professionnel, orienté décision. Utilise le vouvoiement. Pas de jargon technique excessif."
        )
        
        user_prompt = f"""
Analyse ce risque informatique et reformule-le pour un rapport à la Direction Générale.

DONNÉES TECHNIQUES :
- Titre : {risk_data.get('title')}
- Description : {risk_data.get('description')}
- Menace associée : {risk_data.get('threat')}
- Impact estimé : {risk_data.get('impact')}/5
- Probabilité : {risk_data.get('likelihood')}/5
- Site concerné : {risk_data.get('site')}

CONSIGNE :
Rédige un paragraphe court (max 100 mots) expliquant :
1. Le problème concret (en français simple).
2. L'impact potentiel sur l'activité (production, sécurité des personnes, réputation, finances).
3. Une recommandation claire d'action prioritaire.

Format attendu : Texte brut, sans markdown, prêt à copier-coller dans un email officiel.
"""
        return await self.generate_text(user_prompt, system_prompt)

    async def suggest_iso_controls(self, risk_data: dict) -> List[Dict[str, Any]]:
        """
        Suggère des contre-mesures alignées ISO 27002:2022.
        Retourne une liste structurée de dictionnaires.
        """
        system_prompt = (
            "Tu es un auditeur certifié ISO 27001/27002. "
            "Ta mission est de proposer des mesures correctives concrètes, réalisables et conformes aux normes internationales. "
            "Privilégie les contrôles organisationnels avant les solutions technologiques coûteuses."
        )
        
        user_prompt = f"""
Pour le risque suivant, propose 3 à 5 actions de mitigation concrètes classées par priorité (Haute/Moyenne/Basse).

RISQUE :
- Réf : {risk_data.get('ref')}
- Titre : {risk_data.get('title')}
- Contexte : {risk_data.get('description')}
- Menace : {risk_data.get('threat')}

FORMAT DE RÉPONSE ATTENDU (JSON STRICT UNIQUEMENT) :
[
  {{
    "priority": "Haute",
    "action": "Description courte de l'action",
    "iso_control_ref": "Ex: A.8.9 Configuration Management",
    "estimated_effort": "Faible/Moyen/Fort"
  }}
]

Ne renvoie QUE le tableau JSON, rien d'autre. Pas de texte introductif ni conclusif.
"""
        raw_response = await self.generate_text(user_prompt, system_prompt, temperature=0.3)
        
        # Parsing Robuste du JSON
        try:
            # Nettoyage des balises markdown souvent ajoutées par les LLMs
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            
            # Tentative de parse direct
            parsed_data = json.loads(clean_json)
            
            # Validation basique : doit être une liste
            if isinstance(parsed_data, list):
                return parsed_data
            else:
                raise ValueError("La réponse n'est pas une liste JSON valide.")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"⚠️ Réponse IA non-JSON détectée ({e}). Renvoi fallback.")
            # Fallback : retourner le texte brut enveloppé dans une structure simple
            return [{
                "priority": "Information",
                "action": raw_response,
                "iso_control_ref": "N/A (Réponse brute)",
                "estimated_effort": "À évaluer"
            }]


# Instance singleton accessible partout
ai_service = AIService()