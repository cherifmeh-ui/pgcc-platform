# backend/app/api/v1/endpoints/documents.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import uuid
import re
from datetime import datetime

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.iso_control_evidence import IsoControlEvidence
from app.services.document_extractor import DocumentExtractor
from app.models.user import User
from app.services.security_logger import enqueue_audit_event

# ⬇️ IMPORT DU SERVICE RAG POUR L'INDEXATION VECTORIELLE
try:
    from app.services.rag_service import rag_service
except ImportError:
    rag_service = None # Fallback si le module n'est pas encore déployé

router = APIRouter(prefix="/documents", tags=["Gestion Documentaire"])

# Viewer access is limited to employee-facing policy/procedure material. Contracts,
# audit reports and unknown legacy document types fail closed as RESTRICTED.
INTERNAL_DOCUMENT_TYPES = frozenset({"PSSI", "PROCEDURE", "REGLEMENT_INTERIEUR"})
PRIVILEGED_DOCUMENT_ROLES = frozenset({"admin", "executive", "auditor"})


def document_classification(doc_type: str | None) -> str:
    normalized = (doc_type or "").strip().upper()
    return "INTERNAL" if normalized in INTERNAL_DOCUMENT_TYPES else "RESTRICTED"


def can_read_document(user: User, document: Document) -> bool:
    role = (getattr(user, "role", None) or "").strip().lower()
    if role in PRIVILEGED_DOCUMENT_ROLES:
        return True
    return role == "viewer" and document_classification(document.doc_type) == "INTERNAL"


class DocumentResponse(BaseModel):
    id: str          # String explicite pour éviter les bugs Pydantic v2 stricts
    title: str
    doc_type: str
    classification: str
    filename: str
    version: Optional[str] = None
    author: Optional[str] = None
    file_size_kb: float
    is_indexed: bool
    created_at: str  # ISO String explicite
    
    model_config = ConfigDict(from_attributes=True)


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
    existing_q = await db.execute(
        select(Document).where(
            func.lower(func.btrim(Document.filename)) == safe_filename.lower()
        )
    )
    if existing_q.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Un document portant ce nom existe déjà.")

    # 5. Créer l'objet ORM
    new_doc = Document(
        title=title,
        doc_type=doc_type.strip().upper(), 
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
    try:
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="UPLOAD", resource="documents",
            resource_id=str(new_doc.id), details=f"Document uploaded: {safe_filename}",
            event_type="DOCUMENT", request=request,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Un document portant ce nom existe déjà.",
        ) from exc
    except Exception:
        await db.rollback()
        raise
    await db.refresh(new_doc)
    
    # CONSTRUCTION MANUELLE DE LA RÉPONSE POUR ÉVITER LES BUGS PYDANTIC
    return {
        "id": str(new_doc.id),
        "title": new_doc.title,
        "doc_type": new_doc.doc_type,
        "classification": document_classification(new_doc.doc_type),
        "filename": new_doc.filename,
        "version": new_doc.version,
        "author": new_doc.author,
        "file_size_kb": float(new_doc.file_size_kb or 0),
        "is_indexed": bool(new_doc.is_indexed),
        "created_at": new_doc.created_at.isoformat() if new_doc.created_at else ""
    }


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "read"),
):
    query = select(Document).order_by(Document.created_at.desc())
    if (current_user.role or "").strip().lower() == "viewer":
        query = query.where(
            func.upper(func.btrim(Document.doc_type)).in_(tuple(INTERNAL_DOCUMENT_TYPES))
        )
    result = await db.execute(query)
    docs = result.scalars().all()
    
    # ✅ MAPPING EXPLICITE VERS UN DICTIONNAIRE PYTHON STANDARD
    formatted_docs = []
    for doc in docs:
        formatted_docs.append({
            "id": str(doc.id),
            "title": doc.title,
            "doc_type": doc.doc_type,
            "classification": document_classification(doc.doc_type),
            "filename": doc.filename,
            "version": doc.version,
            "author": doc.author,
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
        
    result = await db.execute(select(Document).where(Document.id == uid).with_for_update())
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")
        
    filename = doc.filename
    evidence_result = await db.execute(
        select(IsoControlEvidence).where(IsoControlEvidence.document_id == doc.id)
    )
    linked_evidence = evidence_result.scalars().all()
    if linked_evidence:
        raise HTTPException(
            status_code=409,
            detail="Ce document est utilisé comme preuve ISO. Retirez ses associations de preuve avant de le supprimer.",
        )
    # Delete child rows in SQL before the parent. Using ORM delete() for each
    # chunk and then deleting the parent can race with the database ON DELETE
    # CASCADE and produce stale-row-count warnings during concurrent cleanup.
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    await db.delete(doc)
    try:
        await db.flush()
        await enqueue_audit_event(
            db, user_email=current_user.email, action="DELETE", resource="documents",
            resource_id=str(uid), details=f"Document deleted: {filename}",
            event_type="DOCUMENT", request=request,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conflit lors de la suppression du document.") from exc
    except Exception:
        await db.rollback()
        raise


# ===================================================================
# NOUVEL ENDPOINT : DÉCLENCHEMENT DE L'INDEXATION VECTORIELLE (RAG)
# ===================================================================
@router.post("/{doc_id}/index", status_code=200)
async def trigger_indexation(
    doc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "update"),
):
    """
    Déclenche l'indexation vectorielle (RAG) d'un document.
    Le traitement est exécuté de manière synchrone dans cette version; le endpoint retourne 200 après son résultat.
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
        success = await rag_service.index_document(
            db, str(uid), user_email=current_user.email, request=request
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Échec de l'indexation documentaire. Vérifiez le service d'embeddings.") from exc
    if success:
        return {"message": f"Indexation réussie pour '{doc.title}'.", "status": "indexed"}
    else:
        raise HTTPException(status_code=500, detail="Échec partiel ou complet de l'indexation.")


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "read"),
):
    """Download the original file after enforcing document-read permission."""
    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invalide")

    result = await db.execute(select(Document).where(Document.id == uid))
    doc = result.scalar_one_or_none()
    if not doc or not can_read_document(current_user, doc):
        raise HTTPException(status_code=404, detail="Document introuvable")
    if not doc.file_data:
        raise HTTPException(status_code=404, detail="Fichier original indisponible.")

    # Filenames are sanitized at upload; quote defensively for HTTP headers.
    filename = (doc.filename or "document").replace('"', "_").replace("\\r", "").replace("\\n", "")
    return Response(
        content=doc.file_data,
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.get("/{doc_id}/preview")
async def preview_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("documents", "read"),
):
    """Return a bounded preview of extracted document text."""
    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invalide")

    result = await db.execute(select(Document).where(Document.id == uid))
    doc = result.scalar_one_or_none()
    if not doc or not can_read_document(current_user, doc):
        raise HTTPException(status_code=404, detail="Document introuvable")

    text_content = doc.content_text or ""
    preview_limit = 20_000
    return {
        "id": str(doc.id),
        "title": doc.title,
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "classification": document_classification(doc.doc_type),
        "version": doc.version,
        "author": doc.author,
        "preview": text_content[:preview_limit],
        "truncated": len(text_content) > preview_limit,
    }
