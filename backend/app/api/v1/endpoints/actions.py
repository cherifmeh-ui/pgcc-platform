# backend/app/api/v1/endpoints/actions.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.action_item import ActionItem, ActionStatus, Priority
from app.models.risk import Risk
from app.models.iso_control import IsoControl
from app.models.iso_control_assessment import IsoControlAssessment
from app.models.action_verification import ActionVerification
from app.models.document import Document
from app.models.user import User
from app.services.security_logger import log_action
from app.services.action_lifecycle import validate_action_transition

router = APIRouter(prefix="/actions", tags=["Plans d'Action"])


# --- SCHÉMAS PYDANTIC ---

class ActionBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10000)
    status: ActionStatus = ActionStatus.TODO
    priority: Priority = Priority.MEDIUM
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    due_date: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le titre de l'action ne peut pas être vide.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ActionCreate(ActionBase):
    risk_id: UUID = Field(..., description="UUID du risque associé")
    iso_control_id: Optional[int] = Field(default=None, gt=0)
    iso_control_ref: Optional[str] = Field(default=None, max_length=50)
    iso_assessment_id: Optional[UUID] = None


class ActionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10000)
    status: Optional[ActionStatus] = None
    priority: Optional[Priority] = None
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    due_date: Optional[datetime] = None
    iso_control_id: Optional[int] = Field(default=None, gt=0)
    iso_control_ref: Optional[str] = Field(default=None, max_length=50)
    iso_assessment_id: Optional[UUID] = None


class ActionResponse(ActionBase):
    id: UUID
    risk_id: UUID
    iso_control_id: Optional[int] = None
    iso_assessment_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ActionVerificationCreate(BaseModel):
    outcome: str
    notes: str = Field(min_length=1, max_length=10000)
    evidence_document_id: Optional[UUID] = None

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        if value not in {"Effective", "Ineffective", "Follow-up required"}:
            raise ValueError("Résultat de vérification invalide.")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Les observations de vérification sont obligatoires.")
        return value


class ActionVerificationResponse(BaseModel):
    id: UUID
    action_id: UUID
    verified_by_id: UUID
    evidence_document_id: Optional[UUID]
    outcome: str
    notes: str
    verified_at: datetime

    class Config:
        from_attributes = True


# --- ENDPOINTS CRUD ---


@router.get("/assignees")
async def list_action_assignees(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "read"),
):
    """Return minimal active-user data for action assignment."""
    result = await db.execute(
        select(User.id, User.email, User.full_name, User.department)
        .where(User.is_active.is_(True))
        .order_by(User.full_name.asc())
    )
    return [
        {"id": str(user.id), "email": user.email, "full_name": user.full_name, "department": user.department}
        for user in result.all()
    ]

@router.get("/", response_model=List[ActionResponse])
async def list_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "read"),
    risk_id: Optional[UUID] = Query(None, description="Filtrer par risque spécifique"),
    iso_control_id: Optional[int] = Query(None, gt=0, description="Filtrer par contrôle ISO"),
    status_filter: Optional[ActionStatus] = Query(None, alias="status", description="Filtrer par statut"),
):
    """Liste toutes les actions, optionnellement filtrées par risque ou statut."""
    query = select(ActionItem).order_by(ActionItem.due_date.asc(), ActionItem.priority.desc())
    
    conditions = []
    if risk_id:
        conditions.append(ActionItem.risk_id == risk_id)
    if iso_control_id:
        conditions.append(ActionItem.iso_control_id == iso_control_id)
    if status_filter:
        conditions.append(ActionItem.status == status_filter)
        
    if conditions:
        query = query.where(and_(*conditions))
        
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    data: ActionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "create"),
):
    """Crée une nouvelle tâche corrective liée à un risque existant."""
    # 1. Vérifier que le risque existe
    risk_check = await db.execute(select(Risk).where(Risk.id == data.risk_id))
    risk = risk_check.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail=f"Risque ID={data.risk_id} introuvable.")
    
    # Resolve ISO control reference into its database ID.
    if data.iso_control_ref:
        control_result = await db.execute(select(IsoControl).where(IsoControl.ref_code == data.iso_control_ref))
        selected_control = control_result.scalar_one_or_none()
        if selected_control is None:
            raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")
        if data.iso_control_id is not None and data.iso_control_id != selected_control.id:
            raise HTTPException(status_code=422, detail="Référence et identifiant du contrôle ISO incohérents.")
        data.iso_control_id = selected_control.id
    # Validate ISO traceability, if provided.
    if data.iso_assessment_id:
        assessment_result = await db.execute(select(IsoControlAssessment).where(IsoControlAssessment.id == data.iso_assessment_id))
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            raise HTTPException(status_code=404, detail="Évaluation ISO introuvable.")
        if data.iso_control_id is not None and assessment.control_id != data.iso_control_id:
            raise HTTPException(status_code=422, detail="L'évaluation ne correspond pas au contrôle ISO sélectionné.")
        data.iso_control_id = assessment.control_id
    if data.iso_control_id is not None:
        control_result = await db.execute(select(IsoControl).where(IsoControl.id == data.iso_control_id))
        if control_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")

    # Enforce a controlled initial state: creation cannot mark work completed.
    if data.status != ActionStatus.TODO:
        raise HTTPException(status_code=422, detail="Une action doit être créée au statut 'À faire'. Les transitions sont réalisées après création.")

    # Validate assigned user if provided.
    if data.assigned_to:
        assignee_result = await db.execute(
            select(User.id).where(User.email == data.assigned_to, User.is_active.is_(True))
        )
        if assignee_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="Le responsable doit correspondre à un utilisateur actif.")

    # 2. Créer l'action
    action_dict = data.model_dump(exclude={"risk_id", "iso_control_ref"})
    action = ActionItem(**action_dict, risk_id=data.risk_id)
    db.add(action)
    await db.commit()
    await db.refresh(action)
    await log_action(
        user_email=current_user.email, action="CREATE", resource="actions",
        resource_id=str(action.id), details=f"Action créée: {action.title}",
        event_type="GRC_ACTION", request=request,
    )
    return action


@router.get("/{action_id}/verifications", response_model=List[ActionVerificationResponse])
async def list_action_verifications(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "read"),
):
    action_result = await db.execute(select(ActionItem).where(ActionItem.id == action_id))
    if action_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Action non trouvée.")
    result = await db.execute(
        select(ActionVerification)
        .where(ActionVerification.action_id == action_id)
        .order_by(ActionVerification.verified_at.desc())
    )
    return result.scalars().all()


@router.post("/{action_id}/verifications", response_model=ActionVerificationResponse, status_code=status.HTTP_201_CREATED)
async def verify_action_effectiveness(
    action_id: UUID,
    data: ActionVerificationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "update"),
):
    action_result = await db.execute(select(ActionItem).where(ActionItem.id == action_id))
    action = action_result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Action non trouvée.")
    if action.status != ActionStatus.DONE:
        raise HTTPException(status_code=409, detail="La vérification d'efficacité est possible uniquement après clôture de l'action.")
    if data.evidence_document_id:
        document_result = await db.execute(select(Document).where(Document.id == data.evidence_document_id))
        document = document_result.scalar_one_or_none()
        if document is None:
            raise HTTPException(status_code=404, detail="Document de preuve introuvable.")
        if not document.file_data:
            raise HTTPException(status_code=422, detail="Le document ne possède pas de fichier source.")
    verification = ActionVerification(
        action_id=action.id,
        verified_by_id=current_user.id,
        evidence_document_id=data.evidence_document_id,
        outcome=data.outcome,
        notes=data.notes,
    )
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    await log_action(
        user_email=current_user.email, action="VERIFY_EFFECTIVENESS", resource="action_verifications",
        resource_id=str(verification.id), details=f"Action {action.id}: {data.outcome}",
        event_type="GRC_ACTION", request=request,
    )
    return verification


@router.put("/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: UUID,
    data: ActionUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "update"),
):
    """Met à jour une action existante (titre, statut, deadline...)."""
    result = await db.execute(select(ActionItem).where(ActionItem.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action non trouvée.")
    
    # Validate effective state before applying a partial update.
    update_data = data.model_dump(exclude_unset=True)
    effective_status = update_data.get("status", action.status)
    effective_description = update_data.get("description", action.description)
    if effective_status == ActionStatus.DONE and not (effective_description or "").strip():
        raise HTTPException(status_code=422, detail="La clôture d'une action exige une description documentant la réalisation. Une preuve formelle sera ajoutée au workflow GRC.")
    if effective_status != action.status:
        try:
            validate_action_transition(action.status, effective_status)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Explicitly clearing ISO traceability clears both linked fields.
    if "iso_control_ref" in update_data and not update_data["iso_control_ref"]:
        update_data["iso_control_id"] = None
        update_data["iso_assessment_id"] = None
    # Resolve the human-readable ISO control reference.
    if update_data.get("iso_control_ref"):
        control_result = await db.execute(select(IsoControl).where(IsoControl.ref_code == update_data["iso_control_ref"]))
        selected_control = control_result.scalar_one_or_none()
        if selected_control is None:
            raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")
        if update_data.get("iso_control_id") not in (None, selected_control.id):
            raise HTTPException(status_code=422, detail="Référence et identifiant du contrôle ISO incohérents.")
        update_data["iso_control_id"] = selected_control.id
    # Validate ISO references and preserve control/assessment consistency.
    effective_control_id = update_data.get("iso_control_id", action.iso_control_id)
    effective_assessment_id = update_data.get("iso_assessment_id", action.iso_assessment_id)
    if effective_assessment_id:
        assessment_result = await db.execute(select(IsoControlAssessment).where(IsoControlAssessment.id == effective_assessment_id))
        assessment = assessment_result.scalar_one_or_none()
        if assessment is None:
            raise HTTPException(status_code=404, detail="Évaluation ISO introuvable.")
        if effective_control_id is not None and assessment.control_id != effective_control_id:
            raise HTTPException(status_code=422, detail="L'évaluation ne correspond pas au contrôle ISO sélectionné.")
        update_data["iso_control_id"] = assessment.control_id
    if effective_control_id is not None:
        control_result = await db.execute(select(IsoControl).where(IsoControl.id == effective_control_id))
        if control_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Contrôle ISO introuvable.")

    if "assigned_to" in update_data and update_data["assigned_to"]:
        assignee_result = await db.execute(
            select(User.id).where(User.email == update_data["assigned_to"], User.is_active.is_(True))
        )
        if assignee_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="Le responsable doit correspondre à un utilisateur actif.")

    # Mise à jour partielle (exclude_unset évite d'écraser avec None)
    update_data.pop("iso_control_ref", None)
    for key, value in update_data.items():
        setattr(action, key, value)
        
    await db.commit()
    await db.refresh(action)
    await log_action(
        user_email=current_user.email, action="UPDATE", resource="actions",
        resource_id=str(action.id), details=f"Action mise à jour: {action.title}; statut={action.status.value if action.status else None}",
        event_type="GRC_ACTION", request=request,
    )
    return action


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    action_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("actions", "delete"),
):
    """Supprime définitivement une action."""
    result = await db.execute(select(ActionItem).where(ActionItem.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action non trouvée.")
    
    if action.status == ActionStatus.DONE:
        raise HTTPException(status_code=409, detail="La suppression d'une action terminée est refusée pour préserver la traçabilité.")

    action_id_str = str(action.id)
    action_title = action.title
    await db.delete(action)
    await db.commit()
    await log_action(
        user_email=current_user.email, action="DELETE", resource="actions",
        resource_id=action_id_str, details=f"Action supprimée: {action_title}",
        event_type="GRC_ACTION", request=request,
    )