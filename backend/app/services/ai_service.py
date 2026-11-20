# backend/app/services/ai_service.py
import json
import re
from typing import Optional

import httpx
from app.core.config import settings


class AIService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL or "http://host.docker.internal:11434"
        self.default_model = settings.OLLAMA_MODEL or "phi3:latest"

    async def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        if not settings.AI_ENABLED or settings.AI_PROVIDER != "ollama":
            raise RuntimeError("Assistant IA désactivé. Configurez AI_ENABLED et AI_PROVIDER.")
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 768},
        }
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{self.base_url.rstrip('/')}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                if not text:
                    raise RuntimeError("Ollama a retourné une réponse vide.")
                return text
        except httpx.TimeoutException as exc:
            raise RuntimeError("Timeout de l'IA locale.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Connexion au service IA local impossible.") from exc

    async def rewrite_risk_for_executive(self, risk_data: dict) -> str:
        prompt = f"""Tu es un conseiller RSSI chargé de présenter les risques au PDG.
Reformule en français professionnel et non technique. N'invente aucun fait.
Présente : scénario, conséquences métier, niveau estimé, décision ou action attendue.
Données du risque :
{json.dumps(risk_data, ensure_ascii=False, indent=2)}
"""
        return await self.generate_text(prompt)

    async def suggest_iso_controls(self, risk_data: dict) -> list:
        prompt = f"""Tu es un expert en gestion des risques cyber et ISO/IEC 27002:2022.
Propose uniquement des références de contrôles pertinentes pour ce scénario.
Ne prétends pas que le contrôle est implémenté. Ne fabrique pas de références.
Retourne uniquement un JSON array d'objets avec les clés ref, title, rationale.
Si tu n'es pas certain de la référence, indique-le dans rationale et n'invente pas.
Risque :
{json.dumps(risk_data, ensure_ascii=False, indent=2)}
"""
        raw = await self.generate_text(prompt)
        candidate = raw.strip()
        candidate = re.sub(r"^\s*```(?:json)?", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"```\s*$", "", candidate).strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Réponse IA non conforme au format JSON attendu.") from exc
        if not isinstance(parsed, list):
            raise RuntimeError("La réponse IA doit être une liste JSON.")
        return parsed


ai_service = AIService()
