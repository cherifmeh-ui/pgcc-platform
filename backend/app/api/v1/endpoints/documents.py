# backend/app/api/v1/endpoints/documents.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
import uuid
import re
from datetime import datetime

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.document import Document
from app.services.document_extractor import DocumentExtractor
from app.models.user import User
from app.services.security_logger import log_action

# ⬇️ IMPORT DU SERVICE RAG POUR L'INDEXATION VECTORIELLE
try:
    from app.services.rag_service import rag_service
except ImportError:
    rag_service = None # Fallback si le module n'est pas encore déployé

router = APIRouter(prefix="/documents", tags=["Gestion Documentaire"])


class DocumentResponse(BaseModel):
    id: str          # String explicite pour éviter les bugs Pydantic v2 stricts
    title: str
    doc_type: str
    filename: str
    file_size_kb: float
    is_indexed: bool
    created_at: str  # ISO String explicite
    
    class Config:
        from_attributes = True


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200, description="Titre humain du document"),
    doc_type: str = Form(..., min_length=1, max_length=50, description="Type: PSSI, Procedure, Contrat, Audit_Report"),
    version: Optional[str] = Form(None, max_length=20),
    author: Optional[str] = Form(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "create"),
):
    """
    Uploade un document (PDF/DOCX), extrait son texte et le sauvegarde.
    """
    # Read at most the configured limit plus one byte to avoid unbounded memory use.
    MAX_SIZE_BYTES = 10 * 1024 * 1024
    contents = await file.read(MAX_SIZE_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (Max 10 Mo).")

    raw_filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    safe_filename = re.sub(r"[^A-Za-z0-9._ -]", "_", raw_filename).strip(" .")
    if not safe_filename or len(safe_filename) > 200:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide ou trop long.")
    extension = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if extension not in {"pdf", "docx"}:
        raise HTTPException(status_code=400, detail="Formats autorisés : PDF et DOCX.")

    # Validate file signatures rather than trusting extension or client MIME.
    if extension == "pdf" and not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Signature PDF invalide.")
    if extension == "docx" and not contents.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Signature DOCX invalide.")

    try:
        extracted_text, detected_format = DocumentExtractor.extract_text(contents, safe_filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    size_kb = int((len(contents) + 1023) / 1024)
    existing_q = await db.execute(select(Document).where(Document.filename == safe_filename))
    if existing_q.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Un document portant ce nom existe déjà.")

    # 5. Créer l'objet ORM
    new_doc = Document(
        title=title,
        doc_type=doc_type.upper(), 
        version=version,
        author=author,
        filename=safe_filename,
        content_text=extracted_text,
        file_data=contents, # Stocker le binaire aussi (utile pour download futur)
        file_size_kb=size_kb,
        mime_type="application/pdf" if detected_format == "PDF" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        is_indexed=False # Pas encore vectorisé
    )
    
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    # ✅ CONSTRUCTION MANUELLE DE LA RÉPONSE POUR ÉVITER LES BUGS PYDANTIC
    return {
        "id": str(new_doc.id),
        "title": new_doc.title,
        "doc_type": new_doc.doc_type,
        "filename": new_doc.filename,
        "file_size_kb": float(new_doc.file_size_kb or 0),
        "is_indexed": bool(new_doc.is_indexed),
        "created_at": new_doc.created_at.isoformat() if new_doc.created_at else ""
    }


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "read"),
):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    
    # ✅ MAPPING EXPLICITE VERS UN DICTIONNAIRE PYTHON STANDARD
    formatted_docs = []
    for doc in docs:
        formatted_docs.append({
            "id": str(doc.id),
            "title": doc.title,
            "doc_type": doc.doc_type,
            "filename": doc.filename,
            "file_size_kb": float(doc.file_size_kb or 0),
            "is_indexed": bool(doc.is_indexed),
            "created_at": doc.created_at.isoformat() if doc.created_at else ""
        })
        
    return formatted_docs


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "delete"),
):
    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invalide")
        
    result = await db.execute(select(Document).where(Document.id == uid))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")
        
    filename = doc.filename
    await db.delete(doc)
    await db.commit()
    await log_action(
        user_email=current_user.email, action="DELETE", resource="documents",
        resource_id=str(uid), details=f"Document deleted: {filename}",
        event_type="DOCUMENT", request=request,
    )


# ===================================================================
# NOUVEL ENDPOINT : DÉCLENCHEMENT DE L'INDEXATION VECTORIELLE (RAG)
# ===================================================================
@router.post("/{doc_id}/index", status_code=202)
async def trigger_indexation(
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "update"),
):
    """
    Déclenche l'indexation vectorielle (RAG) d'un document.
    Retourne 202 Accepted car le traitement est asynchrone/long.
    """
    if not rag_service:
        raise HTTPException(status_code=503, detail="Service RAG indisponible. Vérifiez que 'rag_service.py' est bien chargé.")

    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invalide")
        
    # Vérifier existence
    result = await db.execute(select(Document).where(Document.id == uid))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")
        
    if doc.is_indexed:
         return {"message": "Document déjà indexé.", "status": "completed"}

    # Lancer l'indexation (Attention : Bloquant si gros volume, idéalement Celery/RQ)
    # Pour MVP Dev, on attend le résultat directement.
    try:
        success = await rag_service.index_document(db, str(uid))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Échec de l'indexation documentaire. Vérifiez le service d'embeddings.") from exc
    if success:
        await log_action(
            user_email=current_user.email, action="INDEX", resource="documents",
            resource_id=str(uid), details=f"Document indexed: {doc.title}",
            event_type="DOCUMENT", request=request,
        )
        return {"message": f"Indexation réussie pour '{doc.title}'.", "status": "indexed"}
    else:
        raise HTTPException(status_code=500, detail="Échec partiel ou complet de l'indexation.")