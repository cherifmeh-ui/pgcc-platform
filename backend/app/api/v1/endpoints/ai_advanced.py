# backend/app/api/v1/endpoints/ai_advanced.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import require_permission
from app.core.database import get_db
from app.models.document import Document
from app.services.ai_service import ai_service # Ton service Ollama actuel

router = APIRouter(prefix="/ai-advanced", tags=["IA Avancée"])

class ContextQueryRequest(BaseModel):
    question: str
    control_ref: str # Ex: "A.5.1"
    include_docs: bool = True

@router.post("/query-context")
async def query_with_context(
    req: ContextQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user = require_permission("ai_assistant", "use")
):
    """
    Pose une question à l'IA en lui fournissant le contexte des documents chargés.
    """
    try:
        # 1. Récupérer les documents pertinents (ex: PSSI)
        docs_prompt = ""
        if req.include_docs:
            # Recherche simple par type 'PSSI' ou titre contenant le controle
            docs_query = await db.execute(
                select(Document).where(
                    (Document.doc_type == "PSSI") | 
                    (Document.content_text.ilike(f"%{req.control_ref}%"))
                ).limit(3) # Limite pour ne pas saturer le prompt
            )
            docs = docs_query.scalars().all()
            
            for d in docs:
                # Tronquer le contenu pour tenir dans le contexte LLM
                snippet = d.content_text[:1500] if d.content_text else "[Contenu vide]"
                docs_prompt += f"\n\n--- DOCUMENT: {d.title} ---\n{snippet}\n----------------------"

        # 2. Construire le Prompt Enrichi
        full_prompt = f"""
Tu es expert ISO 27002 et RSSI CTF.
Question utilisateur : "{req.question}"
Contexte Normatif : Le contrôle concerné est {req.control_ref}.
Documents Internes Disponibles :
{docs_prompt}

Si la réponse se trouve dans les documents fournis, cite-les explicitement.
Sinon, indique que l'information manque dans la documentation actuelle.
Réponds en français professionnel.
"""

        # 3. Appel Ollama
        response = await ai_service.generate_text(full_prompt, model="phi3:latest")
        
        return {"answer": response, "sources_used": len(docs_prompt.split("---")) // 2}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))