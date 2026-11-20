# backend/app/services/ai_service.py
import httpx
from typing import Optional
from app.core.config import settings

class AIService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL or "http://host.docker.internal:11434"
        self.default_model = "phi3:latest" # Modèle rapide pour dev/test
        
    async def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Génère du texte brut via Ollama. Utilisé par le Dashboard DG.
        Gère les timeouts et erreurs réseau silencieusement.
        """
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 512}
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "").strip()
        except Exception as e:
            print(f"⚠️ Erreur appel Ollama generate_text: {e}")
            raise RuntimeError(f"L'IA locale est indisponible ({str(e)[:30]}...)")

    # ... Garde tes méthodes existantes (rewrite_risk_for_executive, suggest_controls, etc.) ...
    async def rewrite_risk_for_executive(self, risk_data: dict) -> str:
        # Implémentation existante inchangée
        pass 

    async def suggest_controls(self, risk_data: dict) -> list:
        # Implémentation existante inchangée
        return []

# Instance globale utilisée par FastAPI DI
ai_service = AIService()