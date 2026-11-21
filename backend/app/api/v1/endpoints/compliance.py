# backend/app/api/v1/endpoints/compliance.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any
from datetime import datetime, timezone
import hashlib
from uuid import UUID

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.iso_control import IsoControl
from app.models.risk import Risk
from app.models.action_item import ActionItem, ActionStatus
from app.models.user import User
from app.models.iso_control_assessment import IsoControlAssessment
from app.models.iso_control_evidence import IsoControlEvidence
from app.models.document import Document
from app.services.security_logger import log_action

router = APIRouter(prefix="/compliance", tags=["Conformité ISO"])

class AssessmentCreate(BaseModel):
    applicability: str
    implementation_status: str
    maturity_level: int = Field(strict=True, ge=0, le=5)
    justification: str = Field(min_length=1, max_length=10000)
    gap_description: str | None = Field(default=None, max_length=10000)

    @field_validator("applicability")
    @classmethod
    def validate_applicability(cls, value: str) -> str:
        if value not in {"Applicable", "Non applicable"}:
            raise ValueError("Applicabilité invalide.")
        return value

    @field_validator("implementation_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"Non démarré", "En cours", "Implémenté", "Partiellement implémenté"}:
            raise ValueError("Statut d'implémentation invalide.")
        return value

    @field_validator("justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Une justification est obligatoire.")
        return value

class AssessmentResponse(BaseModel):
    id: UUID
    control_id: int
    assessed_by_id: UUID
    applicability: str
    implementation_status: str
    maturity_level: int
    justification: str
    gap_description: str | None
    assessed_at: datetime

class EvidenceCreate(BaseModel):
    document_id: UUID
    assessment_id: UUID | None = None
    evidence_owner: str | None = Field(default=None, max_length=150)
    collected_at: datetime | None = None
    valid_until: datetime | None = None
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.valid_until and self.collected_at:
            collected = self.collected_at.replace(tzinfo=timezone.utc) if self.collected_at.tzinfo is None else self.collected_at
            valid_until = self.valid_until.replace(tzinfo=timezone.utc) if self.valid_until.tzinfo is None else self.valid_until
            if valid_until < collected:
                raise ValueError("La date de validité doit être postérieure à la collecte.")
        return self

class EvidenceVerify(BaseModel):
    verification_status: str
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("verification_status")
    @classmethod
    def validate_verification_status(cls, value: str) -> str:
        if value not in {"Verified", "Rejected", "Pending"}:
            raise ValueError("Statut de vérification invalide.")
        return value

class EvidenceResponse(BaseModel):
    id: UUID
    control_id: int
    document_id: UUID
    assessment_id: UUID | None
    evidence_owner: str | None
    collected_at: datetime
    valid_until: datetime | None
    verification_status: str
    verified_by_id: UUID | None
    verified_at: datetime | None
    sha256: str
    notes: str | None
    created_at: datetime
    document_title: str | None = None
    document_filename: str | None = None
    is_expired: bool = False

class ComplianceMatrixRow(BaseModel):
    ref_code: str
    title: str
    domain: str
    status: str # "Déclaré couvert", "À vérifier", "Non évalué"
    linked_risks_count: int
    last_update: str | None
    latest_assessment_status: str | None = None
    latest_assessment_maturity: int | None = None
    latest_assessment_applicability: str | None = None
    latest_assessed_at: datetime | None = None
    evidence_count: int = 0
    verified_evidence_count: int = 0
    expired_evidence_count: int = 0
    
class MatrixResponse(BaseModel):
    total_controls: int
    covered_count: int
    partial_count: int
    uncovered_count: int
    overall_score: float # % declarative manual coverage
    evaluated_count: int
    applicable_count: int
    average_maturity: float | None
    maturity_score: float | None
    evidence_count: int
    verified_evidence_count: int
    expired_evidence_count: int
    rows: List[ComplianceMatrixRow]
    methodology: str

@router.get("/controls/{ref_code}/assessments", response_model=List[AssessmentResponse])
async def list_control_assessments(
    ref_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "read"),
):
    control_result = await db.execute(select(IsoControl).where(IsoControl.ref_code == ref_code))
    control = control_result.scalar_one_or_none()
    if control is None:
        raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")
    result = await db.execute(
        select(IsoControlAssessment)
        .where(IsoControlAssessment.control_id == control.id)
        .order_by(IsoControlAssessment.assessed_at.desc())
    )
    return result.scalars().all()


@router.post("/controls/{ref_code}/assessments", response_model=AssessmentResponse, status_code=201)
async def create_control_assessment(
    ref_code: str,
    payload: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "update"),
):
    control_result = await db.execute(select(IsoControl).where(IsoControl.ref_code == ref_code))
    control = control_result.scalar_one_or_none()
    if control is None:
        raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")
    assessment = IsoControlAssessment(
        control_id=control.id,
        assessed_by_id=current_user.id,
        applicability=payload.applicability,
        implementation_status=payload.implementation_status,
        maturity_level=payload.maturity_level,
        justification=payload.justification,
        gap_description=payload.gap_description.strip() if payload.gap_description else None,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


def evidence_response(evidence: IsoControlEvidence, document: Document) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": evidence.id,
        "control_id": evidence.control_id,
        "document_id": evidence.document_id,
        "assessment_id": evidence.assessment_id,
        "evidence_owner": evidence.evidence_owner,
        "collected_at": evidence.collected_at,
        "valid_until": evidence.valid_until,
        "verification_status": evidence.verification_status,
        "verified_by_id": evidence.verified_by_id,
        "verified_at": evidence.verified_at,
        "sha256": evidence.sha256,
        "notes": evidence.notes,
        "created_at": evidence.created_at,
        "document_title": document.title,
        "document_filename": document.filename,
        "is_expired": bool(evidence.valid_until and evidence.valid_until < now),
    }

@router.get("/controls/{ref_code}/evidence", response_model=List[EvidenceResponse])
async def list_control_evidence(
    ref_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "read"),
):
    control_result = await db.execute(select(IsoControl).where(IsoControl.ref_code == ref_code))
    control = control_result.scalar_one_or_none()
    if control is None:
        raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")
    result = await db.execute(
        select(IsoControlEvidence, Document)
        .join(Document, Document.id == IsoControlEvidence.document_id)
        .where(IsoControlEvidence.control_id == control.id)
        .order_by(IsoControlEvidence.created_at.desc())
    )
    return [evidence_response(evidence, document) for evidence, document in result.all()]


@router.post("/controls/{ref_code}/evidence", response_model=EvidenceResponse, status_code=201)
async def create_control_evidence(
    ref_code: str,
    payload: EvidenceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "update"),
):
    control_result = await db.execute(select(IsoControl).where(IsoControl.ref_code == ref_code))
    control = control_result.scalar_one_or_none()
    if control is None:
        raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")
    document_result = await db.execute(select(Document).where(Document.id == payload.document_id))
    document = document_result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    if not document.file_data:
        raise HTTPException(status_code=422, detail="Le document ne possède pas de fichier source.")
    if payload.valid_until and payload.collected_at and payload.valid_until < payload.collected_at:
        raise HTTPException(status_code=422, detail="La date de validité doit être postérieure à la collecte.")
    if payload.assessment_id:
        assessment_result = await db.execute(
            select(IsoControlAssessment).where(
                IsoControlAssessment.id == payload.assessment_id,
                IsoControlAssessment.control_id == control.id,
            )
        )
        if assessment_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="L'évaluation ne correspond pas au contrôle ISO.")
    duplicate = await db.execute(
        select(IsoControlEvidence).where(
            IsoControlEvidence.document_id == document.id,
            IsoControlEvidence.control_id == control.id,
        )
    )
    if duplicate.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ce document est déjà associé à ce contrôle.")
    evidence = IsoControlEvidence(
        control_id=control.id,
        document_id=document.id,
        assessment_id=payload.assessment_id,
        evidence_owner=payload.evidence_owner.strip() if payload.evidence_owner else None,
        collected_at=payload.collected_at or datetime.now(timezone.utc),
        valid_until=payload.valid_until,
        verification_status="Pending",
        sha256=hashlib.sha256(document.file_data).hexdigest(),
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)
    await log_action(
        user_email=current_user.email, action="CREATE", resource="iso_evidence",
        resource_id=str(evidence.id), details=f"Evidence linked to ISO control {ref_code}",
        event_type="COMPLIANCE", request=request,
    )
    return evidence_response(evidence, document)


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_control_evidence(
    evidence_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "update"),
):
    result = await db.execute(
        select(IsoControlEvidence).where(IsoControlEvidence.id == evidence_id)
    )
    evidence = result.scalar_one_or_none()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Preuve introuvable.")
    document_id = str(evidence.document_id)
    control_id = evidence.control_id
    await db.delete(evidence)
    await db.commit()
    await log_action(
        user_email=current_user.email, action="DELETE", resource="iso_evidence",
        resource_id=str(evidence_id), details=f"Evidence removed from ISO control {control_id}; document {document_id}",
        event_type="COMPLIANCE", request=request,
    )


@router.patch("/evidence/{evidence_id}/verify", response_model=EvidenceResponse)
async def verify_control_evidence(
    evidence_id: UUID,
    payload: EvidenceVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "update"),
):
    if payload.verification_status not in {"Verified", "Rejected", "Pending"}:
        raise HTTPException(status_code=422, detail="Statut de vérification invalide.")
    result = await db.execute(
        select(IsoControlEvidence, Document)
        .join(Document, Document.id == IsoControlEvidence.document_id)
        .where(IsoControlEvidence.id == evidence_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Preuve introuvable.")
    evidence, document = row
    evidence.verification_status = payload.verification_status
    evidence.verified_by_id = current_user.id if payload.verification_status != "Pending" else None
    evidence.verified_at = datetime.now(timezone.utc) if payload.verification_status != "Pending" else None
    if payload.notes is not None:
        evidence.notes = payload.notes.strip() or None
    await db.commit()
    await db.refresh(evidence)
    await log_action(
        user_email=current_user.email, action="VERIFY", resource="iso_evidence",
        resource_id=str(evidence.id), details=f"Evidence verification status: {payload.verification_status}",
        event_type="COMPLIANCE", request=request,
    )
    return evidence_response(evidence, document)


@router.get("/matrix", response_model=MatrixResponse)
async def get_compliance_matrix(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("iso27002", "read"),
):
    """Calcule la matrice de conformité ISO 27002 basée sur les risques et actions."""
    try:
        # 1. Fetch all controls
        ctrl_query = await db.execute(select(IsoControl))
        controls = ctrl_query.scalars().all()
        
        if not controls:
             return MatrixResponse(total_controls=0, covered_count=0, partial_count=0, uncovered_count=0, overall_score=0.0, evaluated_count=0, applicable_count=0, average_maturity=None, maturity_score=None, evidence_count=0, verified_evidence_count=0, expired_evidence_count=0, rows=[], methodology="Score déclaratif : seuls les contrôles marqués manuellement sont comptés comme couverts; les liens textuels sont des indicateurs à vérifier.")

        # 2. Fetch relevant risks/actions to determine coverage
        risk_query = await db.execute(select(Risk))
        risks = risk_query.scalars().all()
        
        action_query = await db.execute(select(ActionItem).where(ActionItem.status == ActionStatus.DONE))
        done_actions = action_query.scalars().all()

        evidence_query = await db.execute(select(IsoControlEvidence))
        evidence_by_control = {}
        now_utc = datetime.now(timezone.utc)
        for evidence in evidence_query.scalars().all():
            metrics = evidence_by_control.setdefault(evidence.control_id, {"count": 0, "verified": 0, "expired": 0})
            metrics["count"] += 1
            if evidence.verification_status == "Verified":
                metrics["verified"] += 1
            if evidence.valid_until and evidence.valid_until < now_utc:
                metrics["expired"] += 1

        assessment_query = await db.execute(
            select(IsoControlAssessment).order_by(IsoControlAssessment.assessed_at.desc(), IsoControlAssessment.id.desc())
        )
        latest_assessments = {}
        for assessment in assessment_query.scalars().all():
            latest_assessments.setdefault(assessment.control_id, assessment)

        rows = []
        covered = 0
        partial = 0
        uncovered = 0
        evaluated_count = 0
        applicable_count = 0
        maturity_values = []

        for c in controls:
            latest = latest_assessments.get(c.id)
            if latest:
                evaluated_count += 1
                if latest.applicability == "Applicable":
                    applicable_count += 1
                    maturity_values.append(latest.maturity_level)
            evidence_metrics = evidence_by_control.get(c.id, {"count": 0, "verified": 0, "expired": 0})
            assessment_fields = {
                "latest_assessment_status": latest.implementation_status if latest else None,
                "latest_assessment_maturity": latest.maturity_level if latest else None,
                "latest_assessment_applicability": latest.applicability if latest else None,
                "latest_assessed_at": latest.assessed_at if latest else None,
                "evidence_count": evidence_metrics["count"],
                "verified_evidence_count": evidence_metrics["verified"],
                "expired_evidence_count": evidence_metrics["expired"],
            }
            ref = c.ref_code.lower().strip() # e.g., "a.8.9"
            found_links = 0
            has_done_action = False
            
            # Check manual override first
            if c.is_manually_covered:
                status = "Déclaré couvert"
                covered += 1
                rows.append(ComplianceMatrixRow(
                    ref_code=c.ref_code, title=c.title, domain=c.domain,
                    status=status, linked_risks_count=0, last_update=None,
                    **assessment_fields
                ))
                continue
                
            # Search in Risks (Treatment Plan or Title)
            for r in risks:
                text_blob = f"{r.title} {getattr(r, 'treatment_plan', '')}".lower()
                if ref in text_blob:
                    found_links += 1
                    
            # Search in Done Actions (Title/Desc)
            for a in done_actions:
                text_blob = f"{a.title} {getattr(a, 'description', '')}".lower()
                if ref in text_blob:
                    has_done_action = True
            
            # Determine Status Logic
            if has_done_action or found_links > 0:
                status = "À vérifier"
                partial += 1
            else:
                status = "Non évalué"
                uncovered += 1
                
            rows.append(ComplianceMatrixRow(
                ref_code=c.ref_code, title=c.title, domain=c.domain,
                status=status, linked_risks_count=found_links, last_update=None,
                **assessment_fields
            ))
            
        total = len(rows)
        score = round((covered / total * 100), 1) if total > 0 else 0.0
        maturity_score = round((sum(maturity_values) / (5 * len(maturity_values)) * 100), 1) if maturity_values else None
        
        return MatrixResponse(
            total_controls=total,
            covered_count=covered,
            partial_count=partial,
            uncovered_count=uncovered,
            overall_score=score,
            evaluated_count=evaluated_count,
            applicable_count=applicable_count,
            average_maturity=round(sum(maturity_values) / len(maturity_values), 2) if maturity_values else None,
            maturity_score=maturity_score,
            evidence_count=sum(item["count"] for item in evidence_by_control.values()),
            verified_evidence_count=sum(item["verified"] for item in evidence_by_control.values()),
            expired_evidence_count=sum(item["expired"] for item in evidence_by_control.values()),
            rows=rows,
            methodology="Score déclaratif : seuls les contrôles marqués manuellement sont comptés comme couverts; les liens textuels sont des indicateurs à vérifier."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur lors du calcul de la matrice de conformité.")