"""Supplier register and professional contacts API (TPRM)."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.supplier import Supplier, SupplierContact
from app.models.user import User
from app.services.security_logger import log_action

router = APIRouter(prefix="/suppliers", tags=["Fournisseurs et tiers (TPRM)"])

Level = Literal["Faible", "Moyenne", "Élevée", "Critique"]
SupplierStatus = Literal[
    "À qualifier", "En évaluation", "Approuvé",
    "Approuvé sous conditions", "Suspendu", "Terminé",
]
ContactType = Literal["Commercial", "Technique", "Sécurité", "Contractuel", "Autre"]


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
    current_user: User = require_permission("suppliers", "read"),
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
