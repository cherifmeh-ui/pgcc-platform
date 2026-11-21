# backend/app/api/v1/endpoints/risks.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.risk import Risk
from app.models.action_item import ActionItem
from app.models.user import User
from app.schemas.risk import RiskCreate, RiskResponse, RiskUpdate
from app.services.security_logger import log_action
from app.services.risk_scoring import calculate_risk_level

router = APIRouter(prefix="/risks", tags=["Risques SI"])


@router.get("/", response_model=List[RiskResponse])
async def list_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("risks", "read"),
):
    result = await db.execute(select(Risk).order_by(Risk.risk_level.desc(), Risk.created_at.desc()))
    risks = result.scalars().all()

    return [
        RiskResponse(
            id=risk.id,
            ref=risk.ref,
            title=risk.title,
            description=risk.description,
            threat=risk.threat,
            impact=risk.impact,
            likelihood=risk.likelihood,
            risk_level=risk.risk_level,
            site=risk.site,
            owner_id=risk.owner_id,
            status=risk.status,
            treatment_plan=risk.treatment_plan,
            created_at=risk.created_at.isoformat() if risk.created_at else None,
            updated_at=risk.updated_at.isoformat() if risk.updated_at else None,
        )
        for risk in risks
    ]


@router.post("/", response_model=RiskResponse, status_code=status.HTTP_201_CREATED)
async def create_risk(
    risk_data: RiskCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("risks", "create"),
):
    existing = await db.execute(select(Risk).where(Risk.ref == risk_data.ref))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le risque {risk_data.ref} existe déjà.",
        )

    data = risk_data.model_dump()
    if data.get("owner_id") is not None:
        owner_result = await db.execute(select(User.id).where(User.id == data["owner_id"], User.is_active.is_(True)))
        if owner_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="Le propriétaire du risque n'existe pas ou son compte est inactif.")
    # CALCUL BACKEND DU NIVEAU DE RISQUE (source de vérité)
    data["risk_level"] = calculate_risk_level(data["impact"], data["likelihood"])

    new_risk = Risk(**data)
    db.add(new_risk)
    await db.commit()
    await db.refresh(new_risk)

    await log_action(
        user_email=current_user.email,
        action="CREATE",
        resource="risks",
        resource_id=new_risk.ref,
        details=f"Risque créé: {new_risk.title} (Niveau: {new_risk.risk_level})",
        request=request,
    )

    return RiskResponse(
        id=new_risk.id,
        ref=new_risk.ref,
        title=new_risk.title,
        description=new_risk.description,
        threat=new_risk.threat,
        impact=new_risk.impact,
        likelihood=new_risk.likelihood,
        risk_level=new_risk.risk_level,
        site=new_risk.site,
        owner_id=new_risk.owner_id,
        status=new_risk.status,
        treatment_plan=new_risk.treatment_plan,
        created_at=new_risk.created_at.isoformat() if new_risk.created_at else None,
        updated_at=new_risk.updated_at.isoformat() if new_risk.updated_at else None,
    )


@router.put("/{risk_id}", response_model=RiskResponse)
async def update_risk(
    risk_id: UUID,
    risk_data: RiskUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("risks", "update"),
):
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risque non trouvé.",
        )

    update_data = risk_data.model_dump(exclude_unset=True)

    # Validate the effective state, not only fields present in a partial update.
    effective_status = update_data.get("status", risk.status)
    effective_treatment_plan = update_data.get("treatment_plan", risk.treatment_plan)
    if effective_status in {"En traitement", "Traité", "Accepté"} and not (effective_treatment_plan or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Un risque en traitement, traité ou accepté doit comporter un plan ou une justification documentée.",
        )

    if "owner_id" in update_data and update_data["owner_id"] is not None:
        owner_result = await db.execute(select(User.id).where(User.id == update_data["owner_id"], User.is_active.is_(True)))
        if owner_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="Le propriétaire du risque n'existe pas.")

    # RECALCULER LE NIVEAU SI IMPACT OU LIKELIHOOD CHANGENT
    if "impact" in update_data or "likelihood" in update_data:
        risk.impact = update_data.pop("impact", risk.impact)
        risk.likelihood = update_data.pop("likelihood", risk.likelihood)
        risk.risk_level = calculate_risk_level(risk.impact, risk.likelihood)

    for field, value in update_data.items():
        setattr(risk, field, value)

    await db.commit()
    await db.refresh(risk)

    await log_action(
        user_email=current_user.email,
        action="UPDATE",
        resource="risks",
        resource_id=risk.ref,
        details=f"Risque modifié: {risk.title}",
        request=request,
    )

    return RiskResponse(
        id=risk.id,
        ref=risk.ref,
        title=risk.title,
        description=risk.description,
        threat=risk.threat,
        impact=risk.impact,
        likelihood=risk.likelihood,
        risk_level=risk.risk_level,
        site=risk.site,
        owner_id=risk.owner_id,
        status=risk.status,
        treatment_plan=risk.treatment_plan,
        created_at=risk.created_at.isoformat() if risk.created_at else None,
        updated_at=risk.updated_at.isoformat() if risk.updated_at else None,
    )


@router.delete("/{risk_id}")
async def delete_risk(
    risk_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("risks", "delete"),
):
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risque non trouvé.",
        )

    risk_ref = risk.ref
    risk_title = risk.title

    # Do not cascade-delete treatment actions or their history. Until a formal
    # archive workflow exists, risks with linked actions cannot be hard-deleted.
    action_count_result = await db.execute(
        select(func.count(ActionItem.id)).where(ActionItem.risk_id == risk.id)
    )
    if action_count_result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce risque possède des plans d'action associés. La suppression est refusée afin de préserver la traçabilité. Utilisez une procédure d'archivage.",
        )

    await db.delete(risk)
    await db.commit()

    await log_action(
        user_email=current_user.email,
        action="DELETE",
        resource="risks",
        resource_id=risk_ref,
        details=f"Risque supprimé: {risk_title}",
        request=request,
    )

    return {"message": f"Risque {risk_ref} supprimé"}


@router.get("/owners")
async def list_risk_owners(
    db: AsyncSession = Depends(get_db),
    current_user: User = require_permission("risks", "read"),
):
    """Return minimal active-user data for assigning risk ownership."""
    result = await db.execute(
        select(User.id, User.full_name, User.department)
        .where(User.is_active.is_(True))
        .order_by(User.full_name.asc())
    )
    return [
        {"id": str(user.id), "full_name": user.full_name, "department": user.department}
        for user in result.all()
    ]
