# backend/app/api/v1/endpoints/compliance.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any
from datetime import datetime
from uuid import UUID

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.iso_control import IsoControl
from app.models.risk import Risk
from app.models.action_item import ActionItem, ActionStatus
from app.models.user import User
from app.models.iso_control_assessment import IsoControlAssessment

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
    
class MatrixResponse(BaseModel):
    total_controls: int
    covered_count: int
    partial_count: int
    uncovered_count: int
    overall_score: float # % declarative manual coverage
    evaluated_count: int
    applicable_count: int
    average_maturity: float | None
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
             return MatrixResponse(total_controls=0, covered_count=0, partial_count=0, uncovered_count=0, overall_score=0.0, evaluated_count=0, applicable_count=0, average_maturity=None, rows=[], methodology="Score déclaratif : seuls les contrôles marqués manuellement sont comptés comme couverts; les liens textuels sont des indicateurs à vérifier.")

        # 2. Fetch relevant risks/actions to determine coverage
        risk_query = await db.execute(select(Risk))
        risks = risk_query.scalars().all()
        
        action_query = await db.execute(select(ActionItem).where(ActionItem.status == ActionStatus.DONE))
        done_actions = action_query.scalars().all()

        assessment_query = await db.execute(
            select(IsoControlAssessment).order_by(IsoControlAssessment.assessed_at.desc())
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
            assessment_fields = {
                "latest_assessment_status": latest.implementation_status if latest else None,
                "latest_assessment_maturity": latest.maturity_level if latest else None,
                "latest_assessment_applicability": latest.applicability if latest else None,
                "latest_assessed_at": latest.assessed_at if latest else None,
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
        
        return MatrixResponse(
            total_controls=total,
            covered_count=covered,
            partial_count=partial,
            uncovered_count=uncovered,
            overall_score=score,
            evaluated_count=evaluated_count,
            applicable_count=applicable_count,
            average_maturity=round(sum(maturity_values) / len(maturity_values), 2) if maturity_values else None,
            rows=rows,
            methodology="Score déclaratif : seuls les contrôles marqués manuellement sont comptés comme couverts; les liens textuels sont des indicateurs à vérifier."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur lors du calcul de la matrice de conformité.")