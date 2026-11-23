"""Supplier register and professional contacts API (TPRM)."""
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.supplier import Supplier, SupplierContact, SupplierContract, SupplierAssessment, SupplierAssetLink, SupplierAccessRequest, SupplierAccessReview, SupplierRiskLink, SupplierRiskSnapshot
from app.models.asset import Asset
from app.models.risk import Risk
from app.utils.rbac import role_has_permission
from app.models.document import Document
from app.models.user import User
from app.services.security_logger import log_action
from app.services.supplier_assessment import calculate_assessment_score, get_questionnaire_snapshot, validate_questionnaire, validate_answers

router = APIRouter(prefix="/suppliers", tags=["Fournisseurs et tiers (TPRM)"])


def _supplier_allows_new_asset_link(status: str) -> bool:
    """Suspended or terminated suppliers cannot acquire new asset scope."""
    return status not in ("Suspendu", "Terminé")


def _asset_allows_supplier_access(lifecycle_status: str, retired_at: datetime | None) -> bool:
    """Reject lifecycle statuses or markers that identify retired assets."""
    return lifecycle_status not in ("Retiré", "Décommissionné") and retired_at is None


Level = Literal["Faible", "Moyenne", "Élevée", "Critique"]
SupplierStatus = Literal[
    "À qualifier", "En évaluation", "Approuvé",
    "Approuvé sous conditions", "Suspendu", "Terminé",
]
ContactType = Literal["Commercial", "Technique", "Sécurité", "Contractuel", "Autre"]
ContractType = Literal["Service", "Maintenance", "Hébergement", "Infogérance", "Licence", "Autre"]
ContractStatus = Literal["Brouillon", "En validation", "Actif", "À renouveler", "Expiré", "Résilié"]


class SupplierFields(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    service_category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    business_owner_id: UUID | None = None
    direction: str | None = Field(default=None, max_length=100)
    criticality: Level = "Moyenne"
    dependency_level: Level = "Moyenne"
    data_categories: str | None = None
    hosting_location: str | None = Field(default=None, max_length=200)
    uses_subprocessors: bool = False
    status: SupplierStatus = "À qualifier"

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le code fournisseur ne peut pas être vide")
        return value

    @field_validator("legal_name")
    @classmethod
    def normalize_legal_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La raison sociale ne peut pas être vide")
        return value


class SupplierCreate(SupplierFields):
    pass


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=40)
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    service_category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    business_owner_id: UUID | None = None
    direction: str | None = Field(default=None, max_length=100)
    criticality: Level | None = None
    dependency_level: Level | None = None
    data_categories: str | None = None
    hosting_location: str | None = Field(default=None, max_length=200)
    uses_subprocessors: bool | None = None
    status: SupplierStatus | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Le code fournisseur ne peut pas être vide")
        return value

    @field_validator("legal_name")
    @classmethod
    def normalize_legal_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("La raison sociale ne peut pas être vide")
        return value


class SupplierResponse(SupplierFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime



class SupplierContractFields(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    contract_type: ContractType = "Service"
    description: str | None = None
    start_date: date
    end_date: date | None = None
    notice_period_days: int = Field(default=90, ge=0, le=3650)
    auto_renew: bool = False
    status: ContractStatus = "Brouillon"
    internal_owner_id: UUID | None = None
    document_id: UUID | None = None
    clause_confidentiality: bool = False
    clause_incident_notification: bool = False
    clause_audit_right: bool = False
    clause_business_continuity: bool = False
    clause_reversibility: bool = False
    clause_data_location: bool = False
    clause_subcontracting: bool = False
    clause_data_return_destruction: bool = False

    @field_validator("reference", "title")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ ne peut pas être vide")
        return value

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, value: date | None, info):
        start = info.data.get("start_date")
        if value is not None and start is not None and value < start:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début")
        return value


class SupplierContractCreate(SupplierContractFields):
    pass


class SupplierContractUpdate(BaseModel):
    reference: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    contract_type: ContractType | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    notice_period_days: int | None = Field(default=None, ge=0, le=3650)
    auto_renew: bool | None = None
    status: ContractStatus | None = None
    internal_owner_id: UUID | None = None
    document_id: UUID | None = None
    clause_confidentiality: bool | None = None
    clause_incident_notification: bool | None = None
    clause_audit_right: bool | None = None
    clause_business_continuity: bool | None = None
    clause_reversibility: bool | None = None
    clause_data_location: bool | None = None
    clause_subcontracting: bool | None = None
    clause_data_return_destruction: bool | None = None


class SupplierContractResponse(SupplierContractFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    created_at: datetime
    updated_at: datetime


class SupplierContactCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    role: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    contact_type: ContactType = "Autre"

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le nom du contact ne peut pas être vide")
        return value


class SupplierContactUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    contact_type: ContactType | None = None
    is_active: bool | None = None


class SupplierContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    full_name: str
    role: str | None
    email: str | None
    phone: str | None
    contact_type: ContactType
    is_active: bool



class SupplierAssetLinkCreate(BaseModel):
    asset_id: UUID
    relationship_type: Literal["Héberge", "Maintient", "Administre", "Accède", "Fournit", "Autre"]
    access_level: Literal["Aucun", "Standard", "Privilégié"] = "Aucun"
    data_access: bool = False
    scope: str | None = Field(default=None, max_length=1000)
    review_due_at: date | None = None



class SupplierAccessRequestCreate(BaseModel):
    supplier_asset_link_id: UUID
    access_level: Literal["Standard", "Privilégié"]
    data_access: bool = False
    justification: str = Field(min_length=10, max_length=2000)
    scope: str = Field(min_length=3, max_length=1000)
    start_date: date
    end_date: date
    review_due_at: date

    @field_validator("justification", "scope")
    @classmethod
    def normalize_access_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Le motif et le périmètre doivent être renseignés")
        return value

    @field_validator("end_date")
    @classmethod
    def validate_access_dates(cls, value: date, info):
        start = info.data.get("start_date")
        if start and value < start:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début")
        return value

    @field_validator("review_due_at")
    @classmethod
    def validate_review_date(cls, value: date, info):
        start, end = info.data.get("start_date"), info.data.get("end_date")
        if start and end and not start <= value <= end:
            raise ValueError("La revue doit être comprise dans la période d'accès")
        return value


class SupplierAccessDecision(BaseModel):
    decision: Literal["Approuvé", "Refusé"]
    comment: str = Field(min_length=5, max_length=2000)

    @field_validator("comment")
    @classmethod
    def normalize_decision_comment(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Un commentaire de décision est obligatoire")
        return value


class SupplierAccessRevocation(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_revocation_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Le motif de révocation est obligatoire")
        return value




class SupplierRiskLinkCreate(BaseModel):
    risk_id: UUID
    relationship_type: Literal["Dépendance opérationnelle", "Hébergement", "Maintenance", "Accès aux données", "Accès privilégié", "Sous-traitance", "Autre"]
    relationship_context: str = Field(min_length=5, max_length=2000)

    @field_validator("relationship_context")
    @classmethod
    def normalize_relationship_context(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Le contexte de dépendance doit être renseigné")
        return value


class SupplierRiskLinkResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    risk_id: UUID
    relationship_type: str
    relationship_context: str
    created_by_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierAccessReviewCreate(BaseModel):
    outcome: Literal["Maintenue", "Réduite", "Révoquée"]
    comment: str = Field(min_length=5, max_length=2000)
    next_review_at: date | None = None
    new_access_level: Literal["Standard", "Privilégié"] | None = None
    new_data_access: bool | None = None

    @field_validator("comment")
    @classmethod
    def normalize_review_comment(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Un commentaire de revue est obligatoire")
        return value


class SupplierAccessReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    access_request_id: UUID
    reviewed_by_id: UUID
    reviewed_at: datetime
    outcome: str
    comment: str
    previous_access_level: str
    previous_data_access: bool
    resulting_access_level: str
    resulting_data_access: bool
    next_review_at: date | None


class SupplierAccessRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    supplier_asset_link_id: UUID
    asset_id: UUID
    access_level: str
    data_access: bool
    justification: str
    scope: str
    start_date: date
    end_date: date
    review_due_at: date
    status: str
    requested_by_id: UUID
    requested_at: datetime
    decided_by_id: UUID | None
    decided_at: datetime | None
    decision_comment: str | None
    revoked_by_id: UUID | None
    revoked_at: datetime | None
    revocation_reason: str | None
    created_at: datetime
    updated_at: datetime


class AssetSupplierLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    supplier_code: str
    supplier_name: str
    asset_id: UUID
    relationship_type: str
    access_level: str
    data_access: bool
    scope: str | None
    status: str
    review_due_at: date | None


class SupplierAssetLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    asset_id: UUID
    asset_reference: str | None = None
    asset_name: str | None = None
    relationship_type: str
    access_level: str
    data_access: bool
    scope: str | None
    status: str
    review_due_at: date | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime




@router.get("/assets/{asset_id}/suppliers", response_model=list[AssetSupplierLinkResponse])
async def list_asset_suppliers(
    asset_id: UUID,
    include_ended: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_assets"),
):
    asset_result = await db.execute(select(Asset.id).where(Asset.id == asset_id))
    if asset_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    stmt = (
        select(SupplierAssetLink, Supplier.code, Supplier.legal_name)
        .join(Supplier, Supplier.id == SupplierAssetLink.supplier_id)
        .where(SupplierAssetLink.asset_id == asset_id)
    )
    if not include_ended:
        stmt = stmt.where(SupplierAssetLink.status != "Terminé")
    result = await db.execute(stmt.order_by(Supplier.legal_name.asc()))
    return [
        {
            "id": link.id, "supplier_id": link.supplier_id,
            "supplier_code": code, "supplier_name": name,
            "asset_id": link.asset_id, "relationship_type": link.relationship_type,
            "access_level": link.access_level, "data_access": link.data_access,
            "scope": link.scope, "status": link.status, "review_due_at": link.review_due_at,
        }
        for link, code, name in result.all()
    ]



@router.get("/{supplier_id}/access-requests", response_model=list[SupplierAccessRequestResponse])
async def list_supplier_access_requests(
    supplier_id: UUID,
    include_closed: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_access_requests"),
):
    supplier_result = await db.execute(select(Supplier.id).where(Supplier.id == supplier_id))
    if supplier_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    stmt = select(SupplierAccessRequest).where(SupplierAccessRequest.supplier_id == supplier_id)
    if not include_closed:
        stmt = stmt.where(SupplierAccessRequest.status.in_(["Demandé", "Approuvé", "Suspendu"]))
    result = await db.execute(stmt.order_by(SupplierAccessRequest.requested_at.desc()))
    return result.scalars().all()


@router.post("/{supplier_id}/access-requests", response_model=SupplierAccessRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_access_request(
    supplier_id: UUID,
    data: SupplierAccessRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "request_access"),
):
    supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    supplier = supplier_result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou archivé")
    if supplier.status not in ("Approuvé", "Approuvé sous conditions"):
        raise HTTPException(status_code=422, detail="Le fournisseur doit être approuvé avant toute demande d’accès")
    if data.start_date < date.today():
        raise HTTPException(status_code=422, detail="Une demande d’accès ne peut pas être rétroactive")
    link_result = await db.execute(select(SupplierAssetLink).where(
        SupplierAssetLink.id == data.supplier_asset_link_id,
        SupplierAssetLink.supplier_id == supplier_id,
        SupplierAssetLink.status == "Actif",
    ))
    link = link_result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Relation fournisseur-actif active introuvable")
    asset_result = await db.execute(select(Asset).where(Asset.id == link.asset_id))
    asset = asset_result.scalar_one_or_none()
    if asset is None or not _asset_allows_supplier_access(asset.lifecycle_status, asset.retired_at):
        raise HTTPException(status_code=422, detail="L'actif n'est pas éligible à une nouvelle autorisation")
    duplicate = await db.execute(select(SupplierAccessRequest.id).where(
        SupplierAccessRequest.supplier_asset_link_id == link.id,
        SupplierAccessRequest.status.in_(["Demandé", "Approuvé", "Suspendu"]),
    ))
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Une demande ou autorisation non clôturée existe déjà pour cette relation")
    access_request = SupplierAccessRequest(
        supplier_id=supplier_id, supplier_asset_link_id=link.id, asset_id=link.asset_id,
        requested_by_id=current_user.id, **data.model_dump(exclude={"supplier_asset_link_id"}),
    )
    db.add(access_request)
    await db.commit()
    await db.refresh(access_request)
    await log_action(user_email=current_user.email, action="CREATE_SUPPLIER_ACCESS_REQUEST", resource="supplier_access_requests", resource_id=str(access_request.id), details=f"Access requested for supplier {supplier_id}, asset {link.asset_id}", event_type="SUPPLIER", request=request)
    return access_request


@router.post("/{supplier_id}/access-requests/{access_request_id}/decision", response_model=SupplierAccessRequestResponse)
async def decide_supplier_access_request(
    supplier_id: UUID,
    access_request_id: UUID,
    data: SupplierAccessDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "decide_access"),
):
    result = await db.execute(
        select(SupplierAccessRequest)
        .where(
            SupplierAccessRequest.id == access_request_id,
            SupplierAccessRequest.supplier_id == supplier_id,
        )
        .with_for_update()
    )
    access_request = result.scalar_one_or_none()
    if access_request is None:
        raise HTTPException(status_code=404, detail="Demande d'accès introuvable")
    if access_request.status != "Demandé":
        raise HTTPException(status_code=409, detail="Cette demande a déjà été traitée")
    if access_request.requested_by_id == current_user.id:
        raise HTTPException(status_code=403, detail="Le demandeur ne peut pas approuver sa propre demande")
    supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    supplier = supplier_result.scalar_one_or_none()
    link_result = await db.execute(select(SupplierAssetLink).where(
        SupplierAssetLink.id == access_request.supplier_asset_link_id,
        SupplierAssetLink.status == "Actif",
    ))
    link = link_result.scalar_one_or_none()
    if data.decision == "Approuvé":
        if supplier is None or supplier.status not in ("Approuvé", "Approuvé sous conditions") or link is None:
            raise HTTPException(status_code=422, detail="Le fournisseur ou la relation à l’actif n’est plus éligible")
        asset_result = await db.execute(select(Asset).where(Asset.id == access_request.asset_id))
        asset = asset_result.scalar_one_or_none()
        if asset is None or not _asset_allows_supplier_access(asset.lifecycle_status, asset.retired_at):
            raise HTTPException(status_code=422, detail="L'actif n'est plus éligible à une autorisation d'accès")
        if access_request.start_date < date.today() or access_request.end_date < date.today():
            raise HTTPException(status_code=422, detail="La période demandée est échue ou rétroactive")
    access_request.status = data.decision
    access_request.decided_by_id = current_user.id
    access_request.decided_at = datetime.now(timezone.utc)
    access_request.decision_comment = data.comment
    await db.commit()
    await db.refresh(access_request)
    await log_action(user_email=current_user.email, action=f"SUPPLIER_ACCESS_{data.decision.upper()}", resource="supplier_access_requests", resource_id=str(access_request.id), details=f"Decision for supplier access request {access_request.id}: {data.decision}", event_type="SUPPLIER", request=request)
    return access_request



@router.get("/{supplier_id}/access-requests/{access_request_id}/reviews", response_model=list[SupplierAccessReviewResponse])
async def list_supplier_access_reviews(
    supplier_id: UUID,
    access_request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_access_requests"),
):
    request_result = await db.execute(select(SupplierAccessRequest.id).where(
        SupplierAccessRequest.id == access_request_id,
        SupplierAccessRequest.supplier_id == supplier_id,
    ))
    if request_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Autorisation introuvable")
    result = await db.execute(select(SupplierAccessReview).where(
        SupplierAccessReview.access_request_id == access_request_id,
    ).order_by(SupplierAccessReview.reviewed_at.desc(), SupplierAccessReview.id))
    return result.scalars().all()


@router.post("/{supplier_id}/access-requests/{access_request_id}/reviews", response_model=SupplierAccessReviewResponse, status_code=status.HTTP_201_CREATED)
async def review_supplier_access(
    supplier_id: UUID,
    access_request_id: UUID,
    data: SupplierAccessReviewCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "review_access"),
):
    result = await db.execute(select(SupplierAccessRequest).where(
        SupplierAccessRequest.id == access_request_id,
        SupplierAccessRequest.supplier_id == supplier_id,
    ).with_for_update())
    access_request = result.scalar_one_or_none()
    if access_request is None:
        raise HTTPException(status_code=404, detail="Autorisation introuvable")
    if access_request.status != "Approuvé":
        raise HTTPException(status_code=409, detail="Seule une autorisation approuvée peut faire l'objet d'une revue périodique")
    today = date.today()
    if access_request.start_date > today or access_request.end_date < today:
        raise HTTPException(status_code=409, detail="L'autorisation n'est pas actuellement dans sa période de validité")
    if current_user.id in (access_request.requested_by_id, access_request.decided_by_id):
        raise HTTPException(status_code=403, detail="Le demandeur et l'approbateur initial ne peuvent pas réaliser la revue périodique")
    if data.outcome != "Révoquée":
        if data.next_review_at is None or not today <= data.next_review_at <= access_request.end_date:
            raise HTTPException(status_code=422, detail="La prochaine revue doit être comprise entre aujourd'hui et la fin de l'autorisation")
    previous_level, previous_data = access_request.access_level, access_request.data_access
    resulting_level, resulting_data = previous_level, previous_data
    if data.outcome == "Maintenue":
        if data.new_access_level is not None or data.new_data_access is not None:
            raise HTTPException(status_code=422, detail="Une revue maintenue ne peut pas modifier le niveau d'accès")
    elif data.outcome == "Réduite":
        resulting_level = data.new_access_level or previous_level
        resulting_data = data.new_data_access if data.new_data_access is not None else previous_data
        reduced = (previous_level == "Privilégié" and resulting_level == "Standard") or (previous_data and not resulting_data)
        if not reduced or (resulting_level == "Privilégié" and previous_level != "Privilégié") or (resulting_data and not previous_data):
            raise HTTPException(status_code=422, detail="La décision Réduite doit diminuer réellement les privilèges ou supprimer l'accès aux données, sans élévation")
        access_request.access_level = resulting_level
        access_request.data_access = resulting_data
    else:
        if data.new_access_level is not None or data.new_data_access is not None:
            raise HTTPException(status_code=422, detail="Une révocation ne peut pas définir de nouveaux droits")
        access_request.status = "Révoqué"
        access_request.revoked_by_id = current_user.id
        access_request.revoked_at = datetime.now(timezone.utc)
        access_request.revocation_reason = data.comment
    if data.outcome != "Révoquée":
        access_request.review_due_at = data.next_review_at
    review = SupplierAccessReview(
        access_request_id=access_request.id,
        reviewed_by_id=current_user.id,
        outcome=data.outcome,
        comment=data.comment,
        previous_access_level=previous_level,
        previous_data_access=previous_data,
        resulting_access_level=resulting_level,
        resulting_data_access=resulting_data,
        next_review_at=data.next_review_at,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    await log_action(user_email=current_user.email, action="REVIEW_SUPPLIER_ACCESS", resource="supplier_access_reviews", resource_id=str(review.id), details=f"Access review {data.outcome} for authorization {access_request.id}: {data.comment}", event_type="SUPPLIER", request=request)
    return review


@router.post("/{supplier_id}/access-requests/{access_request_id}/revoke", response_model=SupplierAccessRequestResponse)
async def revoke_supplier_access_request(
    supplier_id: UUID,
    access_request_id: UUID,
    data: SupplierAccessRevocation,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "revoke_access"),
):
    result = await db.execute(select(SupplierAccessRequest).where(
        SupplierAccessRequest.id == access_request_id,
        SupplierAccessRequest.supplier_id == supplier_id,
    ).with_for_update())
    access_request = result.scalar_one_or_none()
    if access_request is None:
        raise HTTPException(status_code=404, detail="Demande d'accès introuvable")
    if access_request.status not in ("Approuvé", "Suspendu"):
        raise HTTPException(status_code=409, detail="Seule une autorisation approuvée ou suspendue peut être révoquée")
    access_request.status = "Révoqué"
    access_request.revoked_by_id = current_user.id
    access_request.revoked_at = datetime.now(timezone.utc)
    access_request.revocation_reason = data.reason
    await db.commit()
    await db.refresh(access_request)
    await log_action(user_email=current_user.email, action="REVOKE_SUPPLIER_ACCESS", resource="supplier_access_requests", resource_id=str(access_request.id), details=f"Supplier access revoked: {data.reason}", event_type="SUPPLIER", request=request)
    return access_request


@router.post("/{supplier_id}/access-requests/{access_request_id}/expire", response_model=SupplierAccessRequestResponse)
async def expire_supplier_access_request(
    supplier_id: UUID,
    access_request_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "expire_access"),
):
    result = await db.execute(select(SupplierAccessRequest).where(
        SupplierAccessRequest.id == access_request_id,
        SupplierAccessRequest.supplier_id == supplier_id,
    ))
    access_request = result.scalar_one_or_none()
    if access_request is None:
        raise HTTPException(status_code=404, detail="Autorisation introuvable")
    if access_request.status not in ("Approuvé", "Suspendu"):
        raise HTTPException(status_code=409, detail="Seule une autorisation approuvée ou suspendue peut expirer")
    if access_request.end_date >= date.today():
        raise HTTPException(status_code=409, detail="La date de fin de l’autorisation n’est pas encore dépassée")
    access_request.status = "Expiré"
    await db.commit()
    await db.refresh(access_request)
    await log_action(user_email=current_user.email, action="EXPIRE_SUPPLIER_ACCESS", resource="supplier_access_requests", resource_id=str(access_request.id), details=f"Supplier access expired on {access_request.end_date}", event_type="SUPPLIER", request=request)
    return access_request



@router.get("/{supplier_id}/risks", response_model=list[SupplierRiskLinkResponse])
async def list_supplier_risk_links(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    if not role_has_permission((current_user.role or "").lower(), "risks", "read"):
        raise HTTPException(status_code=403, detail="Accès refusé : permission risks:read requise.")
    supplier_result = await db.execute(select(Supplier.id).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    if supplier_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    result = await db.execute(select(SupplierRiskLink).where(
        SupplierRiskLink.supplier_id == supplier_id
    ).order_by(SupplierRiskLink.created_at.desc()))
    return result.scalars().all()


@router.post("/{supplier_id}/risks", response_model=SupplierRiskLinkResponse, status_code=status.HTTP_201_CREATED)
async def link_supplier_to_risk(
    supplier_id: UUID,
    data: SupplierRiskLinkCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_risks"),
):
    if not role_has_permission((current_user.role or "").lower(), "risks", "update"):
        raise HTTPException(status_code=403, detail="Accès refusé : permission risks:update requise.")
    supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    supplier = supplier_result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    risk_result = await db.execute(select(Risk).where(Risk.id == data.risk_id))
    risk = risk_result.scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risque introuvable")
    link = SupplierRiskLink(
        supplier_id=supplier_id, risk_id=risk.id,
        relationship_type=data.relationship_type,
        relationship_context=data.relationship_context,
        created_by_id=current_user.id,
    )
    db.add(link)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Association fournisseur/risque déjà existante ou contrainte invalide")
    await db.refresh(link)
    await log_action(
        user_email=current_user.email, action="LINK_SUPPLIER_RISK",
        resource="supplier_risk_links", resource_id=str(link.id),
        details=f"Supplier {supplier.code} linked to risk {risk.ref}: {data.relationship_type}",
        event_type="SUPPLIER_RISK", request=request,
    )
    return link


@router.get("/{supplier_id}/assets", response_model=list[SupplierAssetLinkResponse])
async def list_supplier_assets(
    supplier_id: UUID,
    include_ended: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_assets"),
):
    supplier = await db.execute(select(Supplier.id).where(Supplier.id == supplier_id))
    if supplier.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    stmt = (select(SupplierAssetLink, Asset.reference, Asset.name)
        .join(Asset, Asset.id == SupplierAssetLink.asset_id)
        .where(SupplierAssetLink.supplier_id == supplier_id))
    if not include_ended:
        stmt = stmt.where(SupplierAssetLink.status != "Terminé")
    result = await db.execute(stmt.order_by(SupplierAssetLink.created_at.desc()))
    return [
        {**{column.name: getattr(link, column.name) for column in SupplierAssetLink.__table__.columns},
         "asset_reference": reference, "asset_name": name}
        for link, reference, name in result.all()
    ]


@router.post("/{supplier_id}/assets", response_model=SupplierAssetLinkResponse, status_code=status.HTTP_201_CREATED)
async def link_supplier_asset(
    supplier_id: UUID,
    data: SupplierAssetLinkCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_assets"),
):
    supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    supplier = supplier_result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou archivé")
    if not _supplier_allows_new_asset_link(supplier.status):
        raise HTTPException(
            status_code=409,
            detail="Impossible de créer une relation actif avec un fournisseur suspendu ou terminé.",
        )
    asset_result = await db.execute(select(Asset).where(Asset.id == data.asset_id))
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Actif introuvable")
    if not _asset_allows_supplier_access(asset.lifecycle_status, asset.retired_at):
        raise HTTPException(status_code=422, detail="Impossible de rattacher un actif retiré ou décommissionné")
    existing = await db.execute(select(SupplierAssetLink.id).where(
        SupplierAssetLink.supplier_id == supplier_id,
        SupplierAssetLink.asset_id == data.asset_id,
        SupplierAssetLink.relationship_type == data.relationship_type,
    ))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Cette relation fournisseur-actif existe déjà; réactivez-la ou consultez son historique")
    link = SupplierAssetLink(supplier_id=supplier_id, created_by_id=current_user.id, **data.model_dump())
    db.add(link)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Relation fournisseur-actif déjà créée ou contrainte invalide")
    await db.refresh(link)
    await log_action(user_email=current_user.email, action="LINK_SUPPLIER_ASSET", resource="supplier_asset_links", resource_id=str(link.id), details=f"Supplier {supplier_id} linked to asset {data.asset_id} ({data.relationship_type})", event_type="SUPPLIER", request=request)
    return link


@router.post("/{supplier_id}/assets/{link_id}/terminate", response_model=SupplierAssetLinkResponse)
async def terminate_supplier_asset_link(
    supplier_id: UUID,
    link_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_assets"),
):
    result = await db.execute(select(SupplierAssetLink).where(
        SupplierAssetLink.id == link_id,
        SupplierAssetLink.supplier_id == supplier_id,
    ))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Relation fournisseur-actif introuvable")
    if link.status == "Terminé":
        raise HTTPException(status_code=409, detail="Cette relation est déjà terminée")
    open_access = await db.execute(
        select(SupplierAccessRequest.id).where(
            SupplierAccessRequest.supplier_asset_link_id == link_id,
            SupplierAccessRequest.status.in_(("Demandé", "Approuvé", "Suspendu")),
        ).limit(1)
    )
    if open_access.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Relation impossible à terminer : une demande ou autorisation d'accès reste ouverte. Révoquez ou clôturez-la d'abord.",
        )
    link.status = "Terminé"
    await db.commit()
    await db.refresh(link)
    await log_action(user_email=current_user.email, action="TERMINATE_SUPPLIER_ASSET_LINK", resource="supplier_asset_links", resource_id=str(link.id), details=f"Supplier-asset relationship terminated: {link.id}", event_type="SUPPLIER", request=request)
    return link


@router.get("/", response_model=list[SupplierResponse])
async def list_suppliers(
    search: str | None = Query(default=None, max_length=200),
    criticality: Level | None = None,
    supplier_status: SupplierStatus | None = Query(default=None, alias="status"),
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    stmt = select(Supplier)
    if not include_archived:
        stmt = stmt.where(Supplier.archived_at.is_(None))
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(Supplier.code.ilike(term), Supplier.legal_name.ilike(term), Supplier.trade_name.ilike(term)))
    if criticality:
        stmt = stmt.where(Supplier.criticality == criticality)
    if supplier_status:
        stmt = stmt.where(Supplier.status == supplier_status)
    result = await db.execute(stmt.order_by(Supplier.legal_name.asc(), Supplier.id).limit(limit).offset(offset))
    return result.scalars().all()


@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "create"),
):
    if data.business_owner_id is not None:
        owner = await db.execute(select(User.id).where(User.id == data.business_owner_id, User.is_active.is_(True)))
        if owner.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Responsable métier introuvable ou inactif")
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Code fournisseur déjà utilisé ou contrainte invalide")
    await db.refresh(supplier)
    await log_action(user_email=current_user.email, action="CREATE", resource="suppliers", resource_id=str(supplier.id), details=f"Supplier created: {supplier.code}", event_type="SUPPLIER", request=request)
    return supplier



@router.get("/overview/risk")
async def get_supplier_risk_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    """Return aggregate TPRM indicators without changing central risk scores."""
    if not role_has_permission((current_user.role or "").lower(), "risks", "read"):
        raise HTTPException(status_code=403, detail="La permission risks:read est requise pour consulter la synthèse consolidée.")

    from app.services.supplier_risk_overview import build_supplier_risk_overview

    supplier_rows = await db.execute(
        select(Supplier.id, Supplier.criticality, Supplier.archived_at, Supplier.status)
    )
    suppliers = [
        {"id": row.id, "criticality": row.criticality, "archived": row.archived_at is not None, "status": row.status}
        for row in supplier_rows.all()
    ]
    active_supplier_ids = [item["id"] for item in suppliers if not item["archived"] and item.get("status") != "Terminé"]
    if not active_supplier_ids:
        return build_supplier_risk_overview([], [], [], [], [])

    risk_rows = await db.execute(
        select(SupplierRiskLink.risk_id, Risk.risk_level, Risk.status)
        .join(Risk, Risk.id == SupplierRiskLink.risk_id)
        .where(SupplierRiskLink.supplier_id.in_(active_supplier_ids))
    )
    supplier_risks = [
        {"risk_id": row.risk_id, "risk_level": row.risk_level, "status": row.status}
        for row in risk_rows.all()
    ]

    assessment_rows = await db.execute(
        select(
            SupplierAssessment.supplier_id, SupplierAssessment.status,
            SupplierAssessment.next_review_at, SupplierAssessment.created_at,
        )
        .where(SupplierAssessment.supplier_id.in_(active_supplier_ids))
        .order_by(SupplierAssessment.created_at.desc())
    )
    assessments = [
        {"supplier_id": row.supplier_id, "status": row.status,
         "next_review_at": row.next_review_at, "created_at": row.created_at}
        for row in assessment_rows.all()
    ]

    access_rows = await db.execute(
        select(
            SupplierAccessRequest.status, SupplierAccessRequest.access_level,
            SupplierAccessRequest.start_date, SupplierAccessRequest.end_date,
            SupplierAccessRequest.review_due_at,
        )
        .where(SupplierAccessRequest.supplier_id.in_(active_supplier_ids))
    )
    access_requests = [
        {"status": row.status, "access_level": row.access_level,
         "start_date": row.start_date, "end_date": row.end_date,
         "review_due_at": row.review_due_at}
        for row in access_rows.all()
    ]

    contract_rows = await db.execute(
        select(
            SupplierContract.status, SupplierContract.end_date,
            SupplierContract.clause_confidentiality,
            SupplierContract.clause_incident_notification,
            SupplierContract.clause_audit_right,
            SupplierContract.clause_business_continuity,
            SupplierContract.clause_reversibility,
            SupplierContract.clause_data_location,
            SupplierContract.clause_subcontracting,
            SupplierContract.clause_data_return_destruction,
        )
        .where(SupplierContract.supplier_id.in_(active_supplier_ids))
    )
    contracts = [
        {"status": row.status, "end_date": row.end_date,
         "clause_confidentiality": row.clause_confidentiality,
         "clause_incident_notification": row.clause_incident_notification,
         "clause_audit_right": row.clause_audit_right,
         "clause_business_continuity": row.clause_business_continuity,
         "clause_reversibility": row.clause_reversibility,
         "clause_data_location": row.clause_data_location,
         "clause_subcontracting": row.clause_subcontracting,
         "clause_data_return_destruction": row.clause_data_return_destruction}
        for row in contract_rows.all()
    ]

    return build_supplier_risk_overview(
        suppliers, supplier_risks, assessments, access_requests, contracts
    )


@router.post("/overview/snapshots/capture", status_code=status.HTTP_201_CREATED)
async def capture_supplier_risk_snapshot(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_risks"),
):
    """Capture one immutable snapshot for the current calendar month."""
    snapshot_month = date.today().replace(day=1)
    existing = await db.execute(
        select(SupplierRiskSnapshot.id).where(
            SupplierRiskSnapshot.snapshot_month == snapshot_month
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Un instantané existe déjà pour ce mois.")
    indicators = await get_supplier_risk_overview(db=db, current_user=current_user)
    snapshot = SupplierRiskSnapshot(
        snapshot_month=snapshot_month,
        indicators=indicators,
        captured_by_id=current_user.id,
    )
    db.add(snapshot)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Un instantané mensuel existe déjà ou une contrainte est invalide.")
    await db.refresh(snapshot)
    return {
        "id": snapshot.id,
        "snapshot_month": snapshot.snapshot_month,
        "indicators": snapshot.indicators,
        "created_at": snapshot.created_at,
    }


@router.get("/overview/snapshots")
async def list_supplier_risk_snapshots(
    limit: int = Query(default=24, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    """List historical monthly supplier risk indicators."""
    if not role_has_permission((current_user.role or "").lower(), "risks", "read"):
        raise HTTPException(status_code=403, detail="La permission risks:read est requise.")
    result = await db.execute(
        select(SupplierRiskSnapshot)
        .order_by(SupplierRiskSnapshot.snapshot_month.desc())
        .limit(limit)
    )
    return [
        {
            "id": item.id,
            "snapshot_month": item.snapshot_month,
            "indicators": item.indicators,
            "created_at": item.created_at,
        }
        for item in result.scalars().all()
    ]




@router.get("/overview/concentration")
async def get_supplier_risk_concentration(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    """Identify suppliers concentrating linked central risks and privileged access."""
    if not role_has_permission((current_user.role or "").lower(), "risks", "read"):
        raise HTTPException(status_code=403, detail="La permission risks:read est requise.")
    from app.services.supplier_risk_overview import build_supplier_risk_concentration

    risk_result = await db.execute(
        select(
            Supplier.id.label("supplier_id"), Supplier.code.label("supplier_code"),
            Supplier.legal_name.label("supplier_name"), Supplier.criticality,
            Risk.id.label("risk_id"), Risk.risk_level,
        )
        .join(SupplierRiskLink, SupplierRiskLink.supplier_id == Supplier.id)
        .join(Risk, Risk.id == SupplierRiskLink.risk_id)
        .where(Supplier.archived_at.is_(None), Supplier.status != "Terminé")
    )
    risk_rows = [dict(row._mapping) for row in risk_result.all()]
    access_result = await db.execute(
        select(
            SupplierAccessRequest.supplier_id,
            SupplierAccessRequest.access_level,
        )
        .join(Supplier, Supplier.id == SupplierAccessRequest.supplier_id)
        .where(
            Supplier.archived_at.is_(None),
            Supplier.status != "Terminé",
            SupplierAccessRequest.status == "Approuvé",
            SupplierAccessRequest.access_level == "Privilégié",
            SupplierAccessRequest.start_date <= date.today(),
            SupplierAccessRequest.end_date >= date.today(),
        )
    )
    access_rows = [dict(row._mapping) for row in access_result.all()]
    return build_supplier_risk_concentration(risk_rows, access_rows)[:limit]


@router.get("/overview/trends")
async def get_supplier_risk_trends(
    limit: int = Query(default=12, ge=2, le=60),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    """Compare the two latest captured monthly TPRM snapshots."""
    if not role_has_permission((current_user.role or "").lower(), "risks", "read"):
        raise HTTPException(status_code=403, detail="La permission risks:read est requise.")
    from app.services.supplier_risk_overview import compare_supplier_risk_snapshots

    result = await db.execute(
        select(SupplierRiskSnapshot)
        .order_by(SupplierRiskSnapshot.snapshot_month.desc())
        .limit(limit)
    )
    snapshots = [
        {"snapshot_month": item.snapshot_month, "indicators": item.indicators}
        for item in result.scalars().all()
    ]
    return compare_supplier_risk_snapshots(snapshots)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read"),
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "update"),
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou archivé")
    changes = data.model_dump(exclude_unset=True)
    requested_status = changes.get("status")
    if requested_status in ("Suspendu", "Terminé") and requested_status != supplier.status:
        active_links = await db.execute(
            select(SupplierAssetLink.id).where(
                SupplierAssetLink.supplier_id == supplier_id,
                SupplierAssetLink.status == "Actif",
            ).limit(1)
        )
        if active_links.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail="Changement de statut impossible : des relations fournisseur-actif sont encore actives. Terminez-les d'abord.",
            )
        open_access = await db.execute(
            select(SupplierAccessRequest.id).where(
                SupplierAccessRequest.supplier_id == supplier_id,
                SupplierAccessRequest.status.in_(("Demandé", "Approuvé", "Suspendu")),
            ).limit(1)
        )
        if open_access.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail="Changement de statut impossible : des demandes ou autorisations d'accès restent ouvertes. Révoquez ou clôturez-les d'abord.",
            )
    if changes.get("business_owner_id") is not None:
        owner = await db.execute(select(User.id).where(User.id == changes["business_owner_id"], User.is_active.is_(True)))
        if owner.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Responsable métier introuvable ou inactif")
    for field, value in changes.items():
        setattr(supplier, field, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Code fournisseur déjà utilisé ou contrainte invalide")
    await db.refresh(supplier)
    await log_action(user_email=current_user.email, action="UPDATE", resource="suppliers", resource_id=str(supplier.id), details=f"Supplier updated: {supplier.code}", event_type="SUPPLIER", request=request)
    return supplier


@router.post("/{supplier_id}/archive", response_model=SupplierResponse)
async def archive_supplier(
    supplier_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "archive"),
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou déjà archivé")
    # Archiving is administrative, not an access-revocation workflow.
    # Require active asset links and open access approvals to be explicitly
    # terminated/revoked first, preserving traceability and decision metadata.
    active_links = await db.execute(
        select(SupplierAssetLink.id).where(
            SupplierAssetLink.supplier_id == supplier_id,
            SupplierAssetLink.status == "Actif",
        ).limit(1)
    )
    if active_links.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Archive impossible : des relations fournisseur-actif sont encore actives. Terminez-les avant l'archivage.",
        )
    open_access = await db.execute(
        select(SupplierAccessRequest.id).where(
            SupplierAccessRequest.supplier_id == supplier_id,
            SupplierAccessRequest.status.in_(("Demandé", "Approuvé", "Suspendu")),
        ).limit(1)
    )
    if open_access.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Archive impossible : des demandes d'accès sont encore ouvertes. Révoquez ou clôturez-les avant l'archivage.",
        )
    supplier.archived_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(supplier)
    await log_action(user_email=current_user.email, action="ARCHIVE", resource="suppliers", resource_id=str(supplier.id), details=f"Supplier archived: {supplier.code}", event_type="SUPPLIER", request=request)
    return supplier


@router.get("/{supplier_id}/contacts", response_model=list[SupplierContactResponse])
async def list_supplier_contacts(
    supplier_id: UUID,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_contacts"),
):
    supplier_result = await db.execute(select(Supplier.id).where(Supplier.id == supplier_id))
    if supplier_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    stmt = select(SupplierContact).where(SupplierContact.supplier_id == supplier_id)
    if not include_inactive:
        stmt = stmt.where(SupplierContact.is_active.is_(True))
    result = await db.execute(stmt.order_by(SupplierContact.full_name.asc()))
    return result.scalars().all()


@router.post("/{supplier_id}/contacts", response_model=SupplierContactResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_contact(
    supplier_id: UUID,
    data: SupplierContactCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_contacts"),
):
    supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    if supplier_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou archivé")
    contact = SupplierContact(supplier_id=supplier_id, **data.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    await log_action(user_email=current_user.email, action="CREATE_CONTACT", resource="supplier_contacts", resource_id=str(contact.id), details=f"Supplier contact created for supplier {supplier_id}", event_type="SUPPLIER", request=request)
    return contact


@router.patch("/{supplier_id}/contacts/{contact_id}", response_model=SupplierContactResponse)
async def update_supplier_contact(
    supplier_id: UUID,
    contact_id: UUID,
    data: SupplierContactUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_contacts"),
):
    result = await db.execute(select(SupplierContact).where(SupplierContact.id == contact_id, SupplierContact.supplier_id == supplier_id))
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact fournisseur introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    await db.commit()
    await db.refresh(contact)
    await log_action(user_email=current_user.email, action="UPDATE_CONTACT", resource="supplier_contacts", resource_id=str(contact.id), details=f"Supplier contact updated for supplier {supplier_id}", event_type="SUPPLIER", request=request)
    return contact


AssessmentType = Literal["Initiale", "Périodique", "Renouvellement", "Incident", "Changement majeur"]
AssessmentDecision = Literal["Approuvé", "Approuvé sous conditions", "Refusé"]


class AssessmentQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=500)
    weight: int = Field(ge=1, le=10)
    max_score: int = Field(default=5, ge=1, le=5)
    required: bool = True


class AssessmentAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    score: int = Field(ge=0, le=5)
    comment: str | None = Field(default=None, max_length=4000)
    evidence_document_id: UUID | None = None


class SupplierAssessmentCreate(BaseModel):
    assessment_type: AssessmentType = "Initiale"
    scope: str = Field(min_length=5, max_length=4000)
    questionnaire_version: str = Field(min_length=1, max_length=50)
    next_review_at: date | None = None

    @field_validator("scope", "questionnaire_version")
    @classmethod
    def trim_assessment_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ ne peut pas être vide")
        return value


class SupplierAssessmentAnswers(BaseModel):
    answers: list[AssessmentAnswer] = Field(max_length=100)

    @field_validator("answers")
    @classmethod
    def unique_answer_ids(cls, value):
        ids = [item.question_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Une question ne peut recevoir qu'une réponse")
        return value


class SupplierAssessmentValidation(BaseModel):
    decision: AssessmentDecision
    validation_comment: str = Field(min_length=5, max_length=4000)
    next_review_at: date | None = None


class SupplierAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    assessment_type: AssessmentType
    scope: str
    questionnaire_version: str
    questionnaire_snapshot: list[dict]
    answers: list[dict]
    status: str
    score: float | None
    risk_level: str | None
    decision: str | None
    assessed_by_id: UUID
    validated_by_id: UUID | None
    next_review_at: date | None
    submitted_at: datetime | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


@router.get("/{supplier_id}/contracts", response_model=list[SupplierContractResponse])
async def list_supplier_contracts(
    supplier_id: UUID,
    include_ended: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_contracts"),
):
    supplier_result = await db.execute(select(Supplier.id).where(Supplier.id == supplier_id))
    if supplier_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    stmt = select(SupplierContract).where(SupplierContract.supplier_id == supplier_id)
    if not include_ended:
        stmt = stmt.where(SupplierContract.status.notin_(["Expiré", "Résilié"]))
    result = await db.execute(
        stmt.order_by(SupplierContract.end_date.asc().nullslast(), SupplierContract.reference.asc())
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.post("/{supplier_id}/contracts", response_model=SupplierContractResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_contract(
    supplier_id: UUID,
    data: SupplierContractCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_contracts"),
):
    supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    if supplier_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou archivé")
    if data.internal_owner_id is not None:
        owner = await db.execute(select(User.id).where(User.id == data.internal_owner_id, User.is_active.is_(True)))
        if owner.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Responsable contractuel introuvable ou inactif")
    if data.document_id is not None:
        document = await db.execute(select(Document.id).where(Document.id == data.document_id))
        if document.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Document contractuel introuvable")
    contract = SupplierContract(supplier_id=supplier_id, **data.model_dump())
    db.add(contract)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Référence contractuelle déjà utilisée ou contrainte invalide")
    await db.refresh(contract)
    await log_action(user_email=current_user.email, action="CREATE_CONTRACT", resource="supplier_contracts", resource_id=str(contract.id), details=f"Contract created for supplier {supplier_id}: {contract.reference}", event_type="SUPPLIER", request=request)
    return contract


@router.patch("/{supplier_id}/contracts/{contract_id}", response_model=SupplierContractResponse)
async def update_supplier_contract(
    supplier_id: UUID,
    contract_id: UUID,
    data: SupplierContractUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "manage_contracts"),
):
    result = await db.execute(select(SupplierContract).where(SupplierContract.id == contract_id, SupplierContract.supplier_id == supplier_id))
    contract = result.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contrat fournisseur introuvable")
    changes = data.model_dump(exclude_unset=True)
    proposed_start = changes.get("start_date", contract.start_date)
    proposed_end = changes.get("end_date", contract.end_date)
    if proposed_end is not None and proposed_end < proposed_start:
        raise HTTPException(status_code=422, detail="La date de fin doit être postérieure ou égale à la date de début")
    if changes.get("internal_owner_id") is not None:
        owner = await db.execute(select(User.id).where(User.id == changes["internal_owner_id"], User.is_active.is_(True)))
        if owner.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Responsable contractuel introuvable ou inactif")
    if changes.get("document_id") is not None:
        document = await db.execute(select(Document.id).where(Document.id == changes["document_id"]))
        if document.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Document contractuel introuvable")
    for field, value in changes.items():
        setattr(contract, field, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Référence contractuelle déjà utilisée ou contrainte invalide")
    await db.refresh(contract)
    await log_action(user_email=current_user.email, action="UPDATE_CONTRACT", resource="supplier_contracts", resource_id=str(contract.id), details=f"Contract updated: {contract.reference}", event_type="SUPPLIER", request=request)
    return contract




@router.get("/{supplier_id}/assessments", response_model=list[SupplierAssessmentResponse])
async def list_supplier_assessments(
    supplier_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "read_assessments"),
):
    supplier = await db.execute(select(Supplier.id).where(Supplier.id == supplier_id))
    if supplier.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    result = await db.execute(
        select(SupplierAssessment).where(SupplierAssessment.supplier_id == supplier_id)
        .order_by(SupplierAssessment.created_at.desc(), SupplierAssessment.id)
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.post("/{supplier_id}/assessments", response_model=SupplierAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_assessment(
    supplier_id: UUID,
    data: SupplierAssessmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "assess"),
):
    supplier = await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.archived_at.is_(None)))
    if supplier.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable ou archivé")
    try:
        snapshot = get_questionnaire_snapshot(data.questionnaire_version)
        validate_questionnaire(snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    assessment = SupplierAssessment(
        supplier_id=supplier_id,
        assessment_type=data.assessment_type,
        scope=data.scope,
        questionnaire_version=data.questionnaire_version,
        questionnaire_snapshot=snapshot,
        answers=[],
        assessed_by_id=current_user.id,
        next_review_at=data.next_review_at,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    await log_action(user_email=current_user.email, action="CREATE_ASSESSMENT", resource="supplier_assessments", resource_id=str(assessment.id), details=f"Assessment created for supplier {supplier_id}, questionnaire {assessment.questionnaire_version}", event_type="SUPPLIER", request=request)
    return assessment


@router.put("/{supplier_id}/assessments/{assessment_id}/answers", response_model=SupplierAssessmentResponse)
async def save_supplier_assessment_answers(
    supplier_id: UUID,
    assessment_id: UUID,
    data: SupplierAssessmentAnswers,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "assess"),
):
    result = await db.execute(
        select(SupplierAssessment)
        .where(
            SupplierAssessment.id == assessment_id,
            SupplierAssessment.supplier_id == supplier_id,
        )
        .with_for_update()
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Évaluation fournisseur introuvable")
    if assessment.status != "Brouillon":
        raise HTTPException(status_code=409, detail="Une évaluation soumise ne peut plus être modifiée")
    if assessment.assessed_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Seul l'évaluateur désigné peut modifier ses réponses")
    answers = [answer.model_dump(mode="json") for answer in data.answers]
    try:
        validate_answers(assessment.questionnaire_snapshot, answers, require_all_required=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    evidence_ids = [answer["evidence_document_id"] for answer in answers if answer.get("evidence_document_id")]
    if evidence_ids:
        docs = await db.execute(select(Document.id).where(Document.id.in_(evidence_ids)))
        if len(docs.scalars().all()) != len(set(evidence_ids)):
            raise HTTPException(status_code=422, detail="Une ou plusieurs preuves documentaires sont introuvables")
    assessment.answers = answers
    await db.commit()
    await db.refresh(assessment)
    await log_action(user_email=current_user.email, action="UPDATE_ASSESSMENT_ANSWERS", resource="supplier_assessments", resource_id=str(assessment.id), details=f"Assessment answers updated for supplier {supplier_id}", event_type="SUPPLIER", request=request)
    return assessment


@router.post("/{supplier_id}/assessments/{assessment_id}/submit", response_model=SupplierAssessmentResponse)
async def submit_supplier_assessment(
    supplier_id: UUID,
    assessment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "assess"),
):
    result = await db.execute(select(SupplierAssessment).where(
        SupplierAssessment.id == assessment_id,
        SupplierAssessment.supplier_id == supplier_id,
    ))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Évaluation fournisseur introuvable")
    if assessment.status != "Brouillon" or assessment.assessed_by_id != current_user.id:
        raise HTTPException(status_code=409, detail="Évaluation non modifiable ou évaluateur non autorisé")
    try:
        validate_answers(assessment.questionnaire_snapshot, assessment.answers, require_all_required=True)
        score, risk_level = calculate_assessment_score(assessment.questionnaire_snapshot, assessment.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    assessment.score = score
    assessment.risk_level = risk_level
    assessment.status = "À valider"
    assessment.submitted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assessment)
    await log_action(user_email=current_user.email, action="SUBMIT_ASSESSMENT", resource="supplier_assessments", resource_id=str(assessment.id), details=f"Assessment submitted with score {score} and risk {risk_level}", event_type="SUPPLIER", request=request)
    return assessment


@router.post("/{supplier_id}/assessments/{assessment_id}/validate", response_model=SupplierAssessmentResponse)
async def validate_supplier_assessment(
    supplier_id: UUID,
    assessment_id: UUID,
    data: SupplierAssessmentValidation,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("suppliers", "validate_assessment"),
):
    result = await db.execute(select(SupplierAssessment).where(
        SupplierAssessment.id == assessment_id,
        SupplierAssessment.supplier_id == supplier_id,
    ))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Évaluation fournisseur introuvable")
    if assessment.status != "À valider":
        raise HTTPException(status_code=409, detail="Seule une évaluation soumise peut être validée")
    if assessment.assessed_by_id == current_user.id:
        raise HTTPException(status_code=403, detail="L'évaluateur ne peut pas valider sa propre évaluation")
    if data.decision == "Approuvé" and assessment.risk_level in ("Élevé", "Critique"):
        raise HTTPException(status_code=422, detail="Un niveau de risque élevé ou critique exige une décision conditionnelle ou un refus")
    assessment.decision = data.decision
    assessment.validated_by_id = current_user.id
    assessment.validated_at = datetime.now(timezone.utc)
    assessment.next_review_at = data.next_review_at or assessment.next_review_at
    assessment.status = "Validée"
    await db.commit()
    await db.refresh(assessment)
    await log_action(user_email=current_user.email, action="VALIDATE_ASSESSMENT", resource="supplier_assessments", resource_id=str(assessment.id), details=f"Assessment validated: {data.decision}; {data.validation_comment}", event_type="SUPPLIER", request=request)
    return assessment

